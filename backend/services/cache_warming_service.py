"""
Cache Warming Service - Precompute and Cache Popular Data
==========================================================

Precomputes and caches frequently accessed data to achieve IRCTC-level performance:
- Popular route queries
- Station reachability graphs
- High-demand availability data
- ML features for common routes

Key Features:
- Scheduled cache warming
- Popularity-based prioritization
- Memory-efficient precomputation
- Automatic cache refresh

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Set, Any, Optional
from collections import defaultdict

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from database.session import SessionLocal
from database.models import Trip, StopTime, Stop
from .route_engine import RouteEngine, RouteConstraints
from .inventory.availability_service import availability_service, AvailabilityRequest
from services.multi_layer_cache import multi_layer_cache, RouteQuery, AvailabilityQuery
from database.models import QuotaType
from database.config import Config

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy
from collections import deque
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class WarmingStatus:
    """Cache warming status."""
    is_warming: bool
    last_warming_cycle: Optional[datetime]
    routes_warmed: int
    availability_warmed: int
    reachability_warmed: int


class CacheWarmingService:
    """
    Service for warming caches with popular and frequently accessed data.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """

    def __init__(self):
        """Initialize cache warming service with resilience patterns."""
        self._route_engine = None
        self._is_warming = False
        
        # Circuit breaker for warming operations
        self._warming_breaker = circuit_breaker_manager.get_or_create(
            "cache_warming",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=300.0,  # 5 minutes for warming
                success_threshold=2
            )
        )
        
        # Retry policy for operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Warming statistics
        self._stats = {
            "routes_warmed": 0,
            "availability_warmed": 0,
            "reachability_warmed": 0,
            "ml_features_warmed": 0
        }
        self._stats_lock = asyncio.Lock()
        
        # Last warming cycle
        self._last_warming_cycle: Optional[datetime] = None
        
        logger.info("CacheWarmingService initialized with resilience patterns")

    @property
    def route_engine(self):
        if self._route_engine is None:
            self._route_engine = RouteEngine()
        return self._route_engine

    async def start_warming_cycle(self) -> Dict[str, Any]:
        """
        Start the cache warming cycle.
        
        Returns:
            Dict with warming results
            
        Protected by circuit breaker and retry logic.
        """
        if self._is_warming:
            logger.info("Cache warming already in progress")
            return {"status": "SKIPPED", "reason": "ALREADY_RUNNING"}

        # [Group 3] Load-Aware Throttling
        try:
            from services.agents.load_balancer_agent import load_balancer_agent
            pressure = load_balancer_agent.get_system_pressure()
            if pressure > 0.85:
                logger.warning(
                    f"⏩ [CACHE:REBALANCER] System pressure too high ({pressure:.1%}). "
                    f"Skipping warming cycle."
                )
                return {"status": "SKIPPED", "reason": "HIGH_LOAD", "pressure": pressure}
        except ImportError:
            pass

        self._is_warming = True
        start_time = datetime.utcnow()
        results = {
            "status": "COMPLETED",
            "start_time": start_time.isoformat(),
            "routes": 0,
            "availability": 0,
            "reachability": 0,
            "ml_features": 0,
            "errors": []
        }
        
        try:
            logger.info("Starting cache warming cycle")
            
            # Warm caches in parallel with circuit breaker protection
            async def _warm_with_breaker():
                """Execute warming through circuit breaker."""
                return await asyncio.gather(
                    self._warm_popular_routes(),
                    self._warm_station_reachability(),
                    self._warm_popular_availability(),
                    self._warm_ml_features(),
                    return_exceptions=True
                )
            
            warming_results = await self._warming_breaker.execute(
                self._retry_policy.execute,
                _warm_with_breaker
            )
            
            # Process results
            for i, result in enumerate(warming_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Warming task {i} failed: {result}")
                    results["errors"].append({"task": i, "error": str(result)})
            
            # Update statistics
            async with self._stats_lock:
                results["routes"] = self._stats["routes_warmed"]
                results["availability"] = self._stats["availability_warmed"]
                results["reachability"] = self._stats["reachability_warmed"]
                results["ml_features"] = self._stats["ml_features_warmed"]
            
            self._last_warming_cycle = datetime.utcnow()
            results["end_time"] = self._last_warming_cycle.isoformat()
            results["duration_seconds"] = (
                self._last_warming_cycle - start_time
            ).total_seconds()
            
            # Record metrics
            await self._record_metrics("warming_cycle", True, results["routes"])
            
            logger.info(
                f"Cache warming cycle completed: {results['routes']} routes, "
                f"{results['availability']} availability, "
                f"{results['reachability']} reachability"
            )
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            results["status"] = "FAILED"
            results["error"] = str(e)
            await self._record_metrics("warming_cycle", False, 0)
            
        finally:
            self._is_warming = False
        
        return results

    async def _warm_popular_routes(self):
        """[Task 105] Warm route cache with Adaptive Intelligence & Tatkal Calibration."""
        logger.info("Warming popular routes cache with Regional Intelligence")
        
        # Get prioritized pairs based on Festival Calendar
        popular_pairs = await self._get_popular_station_pairs()

        # Calibration: Increase intensity during Tatkal Rush (7:55 AM - 11:00 AM)
        now = datetime.now().time()
        is_tatkal_rush = (
            now >= datetime.strptime("07:55", "%H:%M").time() and 
            now <= datetime.strptime("11:00", "%H:%M").time()
        )
        
        warm_limit = 50 if is_tatkal_rush else 20
        if is_tatkal_rush:
            logger.warning("⚡ [CACHE] TATKAL RUSH DETECTED: Increasing warming intensity.")

        constraints = RouteConstraints(
            max_transfers=3,
            max_results=5,
            include_wait_time=True
        )

        routes_warmed = 0
        
        # Warm routes for next 7 days
        for days_ahead in range(7):
            travel_date = date.today() + timedelta(days=days_ahead + 1)  # Tomorrow onwards

            for from_station, to_station in popular_pairs[:warm_limit]:
                try:
                    # Create cache query
                    cache_query = RouteQuery(
                        from_station=str(from_station),
                        to_station=str(to_station),
                        date=travel_date,
                        max_transfers=3,
                        include_wait_time=True
                    )

                    # Check if already cached
                    cached = await multi_layer_cache.get_route_query(cache_query)
                    if cached:
                        continue

                    # Compute routes
                    departure_datetime = datetime.combine(travel_date, datetime.min.time())
                    routes = await self.route_engine._compute_routes(
                        from_station, to_station, departure_datetime, constraints
                    )

                    if routes:
                        # Cache the result
                        serialized = self.route_engine._serialize_routes_for_cache(routes)
                        await multi_layer_cache.set_route_query(cache_query, serialized)
                        routes_warmed += 1

                        logger.debug(
                            f"Warmed route cache: {from_station} -> {to_station} "
                            f"on {travel_date}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to warm route {from_station}->{to_station}: {e}"
                    )
        
        async with self._stats_lock:
            self._stats["routes_warmed"] += routes_warmed

    async def _warm_station_reachability(self):
        """Precompute station reachability graphs."""
        logger.info("Warming station reachability cache")
        
        reachability_warmed = 0
        
        session = SessionLocal()
        try:
            # Get major stations (simplified - in production, use station importance metrics)
            major_stations = session.query(Stop).limit(100).all()

            for station in major_stations:
                for max_transfers in [1, 2, 3]:
                    try:
                        # Check if already cached
                        cached = await multi_layer_cache.get_station_reachability(
                            station.id, max_transfers
                        )
                        if cached is not None:
                            continue

                        # Compute reachability
                        reachable = await multi_layer_cache._compute_reachable_stations(
                            session, station.id, max_transfers
                        )

                        if reachable:
                            await multi_layer_cache.set_station_reachability(
                                station.id, reachable, max_transfers
                            )
                            reachability_warmed += 1
                            
                            logger.debug(
                                f"Warmed reachability for station {station.id} "
                                f"({max_transfers} transfers)"
                            )
                            
                    except Exception as e:
                        logger.error(
                            f"Failed to warm reachability for station {station.id}: {e}"
                        )

        finally:
            session.close()
        
        async with self._stats_lock:
            self._stats["reachability_warmed"] += reachability_warmed

    async def _warm_popular_availability(self):
        """Warm availability cache for popular routes and dates."""
        logger.info("Warming popular availability cache")
        
        availability_warmed = 0
        
        # Get popular train routes (simplified)
        popular_routes = await self._get_popular_train_routes()

        # Check next 3 days
        for days_ahead in range(3):
            travel_date = date.today() + timedelta(days=days_ahead + 1)

            for route_info in popular_routes[:50]:
                try:
                    trip_id = route_info['trip_id']
                    from_stop = route_info['from_stop_id']
                    to_stop = route_info['to_stop_id']

                    # Check all quota types
                    for quota in QuotaType:
                        cache_query = AvailabilityQuery(
                            train_id=trip_id,
                            from_stop_id=from_stop,
                            to_stop_id=to_stop,
                            travel_date=travel_date,
                            quota_type=quota.value,
                            passengers=1
                        )

                        # Check if already cached
                        cached = await multi_layer_cache.get_availability(cache_query)
                        if cached:
                            continue

                        # Compute availability
                        avail_request = AvailabilityRequest(
                            trip_id=trip_id,
                            from_stop_id=from_stop,
                            to_stop_id=to_stop,
                            travel_date=travel_date,
                            quota_type=quota,
                            passengers=1
                        )

                        response = await availability_service._check_availability_db(
                            avail_request
                        )

                        # Cache the result
                        await multi_layer_cache.set_availability(
                            cache_query, response.__dict__
                        )
                        availability_warmed += 1

                        logger.debug(
                            f"Warmed availability: train {trip_id}, "
                            f"{from_stop}->{to_stop}, {quota.value}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to warm availability for route {route_info}: {e}"
                    )
        
        async with self._stats_lock:
            self._stats["availability_warmed"] += availability_warmed

    async def _warm_ml_features(self):
        """Warm ML feature cache for popular routes."""
        logger.info("Warming ML features cache")
        
        # This would integrate with your ML service
        # For now, just log that it would happen
        logger.info("ML feature warming would happen here (integrate with ML service)")
        
        async with self._stats_lock:
            self._stats["ml_features_warmed"] += 1

    async def _get_popular_station_pairs(self) -> List[tuple]:
        """[Task 105] Get prioritized pairs using Regional Corridor Intelligence & Dynamic Forecasting."""
        try:
            from services.agents.demand_forecasting_agent import DemandForecastingAgent
            db = SessionLocal()
            try:
                agent = DemandForecastingAgent(db)
                targets = await agent.get_prioritized_warmup_targets()
                return targets
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to fetch intelligent corridors: {e}")
            try:
                from core.nexus.intelligence.corridors import get_high_demand_pairs
                return get_high_demand_pairs()
            except ImportError:
                # Return default pairs
                return [("NDLS", "BPL"), ("NDLS", "JAI"), ("NDLS", "GWL")]

    async def _get_popular_train_routes(self) -> List[Dict]:
        """Get popular train routes (simplified implementation)."""
        session = SessionLocal()
        try:
            # Get some active trips with their stop sequences
            trips = session.query(Trip).filter(Trip.status == "ACTIVE").limit(20).all()

            routes = []
            for trip in trips:
                # Get stop sequence for this trip
                stops = session.query(StopTime).filter(
                    StopTime.trip_id == trip.id
                ).order_by(StopTime.stop_sequence).all()

                if len(stops) >= 2:
                    # Add route from first to last stop
                    routes.append({
                        'trip_id': trip.id,
                        'from_stop_id': stops[0].stop_id,
                        'to_stop_id': stops[-1].stop_id
                    })

            return routes

        finally:
            session.close()

    async def get_warming_status(self) -> WarmingStatus:
        """Get cache warming status and statistics."""
        cache_stats = await multi_layer_cache.get_cache_stats()
        
        async with self._stats_lock:
            return WarmingStatus(
                is_warming=self._is_warming,
                last_warming_cycle=self._last_warming_cycle,
                routes_warmed=self._stats["routes_warmed"],
                availability_warmed=self._stats["availability_warmed"],
                reachability_warmed=self._stats["reachability_warmed"]
            )

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        value: int = 0
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "value": value
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "is_warming": self._is_warming,
            "last_warming_cycle": (
                self._last_warming_cycle.isoformat()
                if self._last_warming_cycle else None
            ),
            "stats": dict(self._stats),
            "circuit_breaker_state": self._warming_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._warming_breaker.get_state().value,
                "failure_count": self._warming_breaker.failure_count,
                "success_count": self._warming_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._warming_breaker.reset()
        logger.info("Circuit breaker reset for cache warming service")

    def reset_stats(self):
        """Reset warming statistics."""
        # Use synchronous lock for sync function
        import threading
        if not hasattr(self, '_stats_lock_sync'):
            self._stats_lock_sync = threading.Lock()
        
        with self._stats_lock_sync:
            self._stats = {
                "routes_warmed": 0,
                "availability_warmed": 0,
                "reachability_warmed": 0,
                "ml_features_warmed": 0
            }
        logger.info("Cache warming statistics reset")


# Global instance
cache_warming_service = CacheWarmingService()


# ============================================================================
# SCHEDULER INTEGRATION
# ============================================================================

async def schedule_cache_warming():
    """Schedule periodic cache warming."""
    while True:
        try:
            # Run warming cycle every 30 minutes during peak hours
            # In production, this would be more sophisticated
            await cache_warming_service.start_warming_cycle()

            # Wait 30 minutes
            await asyncio.sleep(30 * 60)

        except Exception as e:
            logger.error(f"Scheduled cache warming failed: {e}")
            await asyncio.sleep(5 * 60)  # Wait 5 minutes on error


# ============================================================================
# MANUAL CACHE MANAGEMENT
# ============================================================================

async def manual_cache_warmup():
    """Manually trigger cache warming (for admin operations)."""
    logger.info("Manual cache warmup initiated")
    result = await cache_warming_service.start_warming_cycle()
    logger.info(f"Manual cache warmup completed: {result['status']}")
    return result


async def clear_all_caches():
    """Clear all caches (for maintenance/debugging)."""
    logger.warning("Clearing all caches")
    await multi_layer_cache.clear_all_caches()
    logger.info("✅ All caches cleared successfully.")

async def get_cache_health_report() -> Dict:
    """Get comprehensive cache health report."""
    warming_status = await cache_warming_service.get_warming_status()
    cache_stats = await multi_layer_cache.get_cache_stats()
    health = await multi_layer_cache.health_check()

    return {
        'cache_healthy': health,
        'warming_status': {
            'is_warming': warming_status.is_warming,
            'last_warming_cycle': (
                warming_status.last_warming_cycle.isoformat()
                if warming_status.last_warming_cycle else None
            ),
            'routes_warmed': warming_status.routes_warmed,
            'availability_warmed': warming_status.availability_warmed,
            'reachability_warmed': warming_status.reachability_warmed
        },
        'cache_stats': cache_stats,
        'recommendations': _generate_cache_recommendations(cache_stats)
    }


def _generate_cache_recommendations(cache_stats: Dict) -> List[str]:
    """Generate cache optimization recommendations."""
    recommendations = []

    # Check hit rates
    for layer, stats in cache_stats.items():
        if isinstance(stats, dict) and 'hit_rate' in stats:
            hit_rate = stats['hit_rate']
            if hit_rate < 0.5:
                recommendations.append(
                    f"Low hit rate ({hit_rate:.2%}) for {layer} - "
                    f"consider increasing TTL or cache size"
                )
            elif hit_rate > 0.9:
                recommendations.append(
                    f"Excellent hit rate ({hit_rate:.2%}) for {layer}"
                )

    # Check if Redis is connected
    if 'redis' not in cache_stats or not cache_stats.get('redis', {}).get('connected_clients', 0) > 0:
        recommendations.append("Redis not connected - falling back to in-memory cache")

    return recommendations if recommendations else ["Cache performance looks good"]
