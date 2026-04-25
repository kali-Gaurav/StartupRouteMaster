import math
import json
import logging
import time
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from database.session import SessionTransit
from database.models import Trip, Booking, StopTime, Stop, TrainLiveUpdate, Route, StationRank
from services.multi_layer_cache import multi_layer_cache
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import retry_async, RetryPolicy
from collections import deque
import asyncio
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger(__name__)

class SafetyService:
    """
    Core engine for passenger safety, emergency detection, and geofencing.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """
    
    DEVIATION_THRESHOLD_KM = 5.0
    STATIONARY_THRESHOLD_MINUTES = 30
    STATIONARY_MOVE_THRESHOLD_KM = 0.5 # 500m movement counts as "moving"

    def __init__(self):
        """Initialize safety service with resilience patterns."""
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "safety_service_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        
        # Additional circuit breakers
        self._redis_circuit_breaker = circuit_breaker(
            name="safety_service_redis",
            failure_threshold=5,
            recovery_timeout=30.0
        )
        
        # Retry policy
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        self._redis_retry_policy = retry_policy(
            max_attempts=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.1,
            max_delay=2.0
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        self._metrics_client = MetricsClient(
            service_name="safety_service",
            default_tags={"component": "emergency"}
        )
        self._metrics_client.gauge("db_circuit_breaker_state", lambda: self._db_breaker.get_state().value if hasattr(self._db_breaker, 'get_state') else 0)
        self._metrics_client.gauge("redis_circuit_breaker_state", lambda: self._redis_circuit_breaker.state.value)
        self._metrics_client.counter("deviation_checks_total")
        self._metrics_client.counter("deviation_checks_deviated")
        self._metrics_client.counter("stationary_checks_total")
        self._metrics_client.counter("stationary_checks_triggered")
        self._metrics_client.counter("dead_zone_predictions_total")
        self._metrics_client.counter("dead_zone_predictions_upcoming")
        self._metrics_client.histogram("check_duration_seconds")
        
        logger.info("SafetyService initialized with resilience patterns")

    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates distance between two points in km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def get_distance_to_path(lat: float, lon: float, path: List[Tuple[float, float]]) -> float:
        """Finds the minimum distance from a point to any point on the polyline."""
        # Filter out invalid (0,0) coords from DB
        valid_path = [p for p in path if p[0] != 0.0 and p[1] != 0.0]
        
        if not valid_path:
            return float('inf')
        
        min_dist = float('inf')
        for p_lat, p_lon in valid_path:
            dist = SafetyService.haversine(lat, lon, p_lat, p_lon)
            if dist < min_dist:
                min_dist = dist
        return min_dist

    @track_metrics(service="safety_service", operation="check_journey_deviation")
    async def check_journey_deviation(self, user_id: str, lat: float, lon: float, db_user: Session) -> Dict[str, Any]:
        """
        Checks if the user is synced with their train's real-time position.
        """
        # 1. Find active booking
        booking = db_user.query(Booking).filter(
            Booking.user_id == user_id,
            Booking.booking_status == 'confirmed'
        ).order_by(Booking.travel_date.desc()).first()

        if not booking or not booking.trip_id:
            return {"status": "no_active_trip"}

        transit_db = SessionTransit()
        try:
            # 2. Get Train Number for this trip
            trip_info = transit_db.query(Route.route_id)\
                .join(Trip, Route.id == Trip.route_id)\
                .filter(Trip.id == booking.trip_id).first()
            
            train_no = trip_info[0] if trip_info else None
            
            # 3. Get Train's Current Real-Time Position
            live_pos = None
            if train_no:
                live_pos = transit_db.query(TrainLiveUpdate)\
                    .filter(TrainLiveUpdate.train_number == train_no)\
                    .order_by(TrainLiveUpdate.recorded_at.desc()).first()

            # 4. Determine "Focus Area" (Current station +/- 1 stops)
            expected_stops = []
            mode = "unknown"
            
            if live_pos:
                # IMPORTANT: Map live station code to its sequence in THIS specific trip
                active_stop = transit_db.query(StopTime.stop_sequence)\
                    .join(Stop, StopTime.stop_id == Stop.id)\
                    .filter(StopTime.trip_id == booking.trip_id, Stop.code == live_pos.station_code).first()
                
                if active_stop:
                    current_trip_seq = active_stop[0]
                    expected_stops = transit_db.query(Stop.latitude, Stop.longitude)\
                        .join(StopTime, Stop.id == StopTime.stop_id)\
                        .filter(
                            StopTime.trip_id == booking.trip_id,
                            StopTime.stop_sequence.between(current_trip_seq - 1, current_trip_seq + 1)
                        ).all()
                    mode = "real-time"
                else:
                    mode = "live-station-not-in-trip"
            
            # Fallback to full path if real-time segmentation fails or is unavailable
            if not expected_stops:
                expected_stops = transit_db.query(Stop.latitude, Stop.longitude)\
                    .join(StopTime, Stop.id == StopTime.stop_id)\
                    .filter(StopTime.trip_id == booking.trip_id).all()
                mode = "full-path-fallback" if not live_pos else f"{mode}-fallback"

            # 5. Calculate Deviation
            path = [(s.latitude, s.longitude) for s in expected_stops]
            dist = self.get_distance_to_path(lat, lon, path)
            deviated = dist > self.DEVIATION_THRESHOLD_KM
            
            return {
                "status": "ok" if not deviated else "deviated",
                "distance_km": round(dist, 3),
                "mode": mode,
                "train_no": train_no,
                "current_seq": live_pos.sequence if live_pos else None
            }
            
        finally:
            transit_db.close()

    @track_metrics(service="safety_service", operation="check_stationary_alert")
    async def check_stationary_alert(self, user_id: str, lat: float, lon: float) -> Dict[str, Any]:
        """
        Detects if a user is stationary in a high-risk zone for too long.
        """
        await multi_layer_cache.initialize()
        if not multi_layer_cache.redis:
            return {"status": "redis_unavailable"}

        key = f"safety:user:{user_id}:pos"
        now_ts = int(datetime.now().timestamp())
        
        # 1. Fetch Previous Position
        raw = await multi_layer_cache.redis.get(key)
        prev_data = json.loads(raw) if raw else None
        
        # 2. Check for Movement
        moved = True
        if prev_data:
            dist = self.haversine(lat, lon, prev_data['lat'], prev_data['lon'])
            if dist < self.STATIONARY_MOVE_THRESHOLD_KM:
                moved = False
        
        # 3. Update Persistence
        new_data = {
            "lat": lat, "lon": lon, 
            "ts": prev_data['ts'] if not moved and prev_data else now_ts
        }
        await multi_layer_cache.redis.setex(key, 3600, json.dumps(new_data))

        if moved:
            return {"status": "moving"}

        stationary_duration_mins = (now_ts - new_data['ts']) // 60
        
        if stationary_duration_mins < self.STATIONARY_THRESHOLD_MINUTES:
            return {"status": "stationary_monitoring", "duration": stationary_duration_mins}

        # 4. Check Risk Zone & Hub Exemption
        transit_db = SessionTransit()
        try:
            # Check if near a major hub (Exemption)
            # Find nearest hub within 2km
            from sqlalchemy import text
            hub = transit_db.execute(text("""
                SELECT s.name FROM stops s 
                JOIN station_rank r ON s.id = r.station_id
                WHERE r.hub_type IN ('major_hub', 'junction')
                  AND (ABS(s.latitude - :lat) < 0.02 AND ABS(s.longitude - :lon) < 0.02)
                LIMIT 1
            """), {"lat": lat, "lon": lon}).fetchone()
            
            if hub:
                return {"status": "stationary_at_hub", "hub_name": hub[0]}

            # Check if in a High Risk Zone
            risk_zone = transit_db.execute(text("""
                SELECT risk_level, description FROM risk_zones
                WHERE (ABS(latitude - :lat) < 0.05 AND ABS(longitude - :lon) < 0.05)
                ORDER BY risk_level DESC LIMIT 1
            """), {"lat": lat, "lon": lon}).fetchone()

            if risk_zone and risk_zone[0] >= 3: # Risk Level 3+
                return {
                    "status": "trigger_sos_countdown",
                    "reason": f"Stationary for {stationary_duration_mins}m in high-risk zone: {risk_zone[1]}",
                    "risk_level": risk_zone[0]
                }

            return {"status": "stationary_warning", "duration": stationary_duration_mins}
            
        finally:
            transit_db.close()

    async def predict_dead_zone(self, lat: float, lon: float, speed_kmh: float = 60.0) -> Dict[str, Any]:
        """
        Predicts if the train is approaching a known signal dead zone.
        """
        transit_db = SessionTransit()
        try:
            from sqlalchemy import text
            # Find nearest dead zone within 20km
            zone = transit_db.execute(text("""
                SELECT description, radius_km, expected_duration_mins, latitude, longitude
                FROM signal_dead_zones
                WHERE (ABS(latitude - :lat) < 0.2 AND ABS(longitude - :lon) < 0.2)
                LIMIT 1
            """), {"lat": lat, "lon": lon}).fetchone()

            if not zone:
                return {"status": "clear"}

            dist = self.haversine(lat, lon, zone[3], zone[4])
            
            # Calculate ETA in minutes (dist / speed * 60)
            eta_mins = (dist / max(speed_kmh, 10.0)) * 60
            
            if eta_mins <= 15:
                # Subtask 19.1: Fetch local emergency directory for the next 100km
                authorities = transit_db.execute(text("""
                    SELECT name, type, contact_number, latitude, longitude
                    FROM emergency_authorities
                    WHERE (ABS(latitude - :lat) < 1.0 AND ABS(longitude - :lon) < 1.0)
                    LIMIT 5
                """), {"lat": lat, "lon": lon}).fetchall()
                
                auth_list = [{
                    "name": a[0], "type": a[1], "phone": a[2],
                    "dist": round(self.haversine(lat, lon, a[3], a[4]), 2)
                } for a in authorities]

                return {
                    "status": "upcoming_dead_zone",
                    "description": zone[0],
                    "eta_mins": round(eta_mins, 1),
                    "expected_duration": zone[2],
                    "offline_directory": auth_list # The Predictive Buffer
                }

            return {"status": "clear", "nearest_zone_km": round(dist, 2)}
            
        finally:
            transit_db.close()

# =========================================================================
# RESILIENCE PATTERNS
# =========================================================================

    async def _record_metrics(self, check_type: str, result: Dict[str, Any]):
        """Record safety check metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "check_type": check_type,
                "status": result.get("status", "unknown"),
                "deviated": result.get("status") == "deviated"
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_checks": 0, "deviation_rate": 0.0}
        
        total = len(self._metrics)
        deviated = sum(1 for m in self._metrics if m.get("deviated", False))
        
        return {
            "total_checks": total,
            "deviation_count": deviated,
            "deviation_rate": deviated / total if total > 0 else 0.0,
            "circuit_breaker_state": self._db_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._db_breaker.get_state().value,
                "failure_count": self._db_breaker.failure_count,
                "success_count": self._db_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for safety service")


# Singleton
safety_service = SafetyService()
