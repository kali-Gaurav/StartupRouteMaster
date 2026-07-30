"""
Algorithm Data Service
Integrates database models with algorithm services.
Handles data flow between models and algorithm components.
Optimized for memory efficiency and minimal API calls.
"""
import logging
from typing import List, Dict, Any, Optional, cast
from datetime import datetime, date, timedelta
from collections import defaultdict
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.engine import Engine, Connection

from database.config import Config

logger = logging.getLogger(__name__)


class AlgorithmDataService:
    """
    Central service for algorithm data operations.
    Optimized for:
    - Batch operations to minimize DB calls
    - Caching to reduce repeated queries
    - Lazy loading for memory efficiency
    """
    
    # Cache TTL settings (in seconds)
    CACHE_TTL_SHORT = 60  # 1 minute
    CACHE_TTL_MEDIUM = 300  # 5 minutes
    CACHE_TTL_LONG = 3600  # 1 hour
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._cache: Dict[str, tuple[Any, datetime]] = {}
    
    def _db(self) -> Session:
        if self.db is None:
            raise RuntimeError("Database session has not been initialized")
        # Debug: check connection
        try:
            bind = self.db.get_bind()
            if bind is not None:
                if isinstance(bind, Engine):
                    url = str(bind.url)
                elif isinstance(bind, Connection) and bind.engine is not None:
                    url = str(bind.engine.url)
                else:
                    url = repr(bind)
                logger.debug(f"AlgorithmDataService using DB: {url.split('@')[-1] if '@' in url else url}")
        except Exception:
            pass
        return self.db

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < self.CACHE_TTL_MEDIUM:
                return value
            del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set cache value with current timestamp."""
        self._cache[key] = (value, datetime.utcnow())
    
    # =========================================================================
    # KNOWLEDGE GRAPH OPERATIONS
    # =========================================================================
    
    def get_station_knowledge(self, station_code: str) -> Optional[Dict]:
        """Get knowledge about a station."""
        cache_key = f"station_knowledge:{station_code}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            from database.algorithm_models import StationKnowledge
            
            db = self._db()
            station = db.query(StationKnowledge).filter(
                StationKnowledge.station_code == station_code
            ).first()
            
            if station:
                result = {
                    "code": station.station_code,
                    "name": station.station_name,
                    "region": station.region,
                    "zone": station.zone,
                    "connectivity_score": station.connectivity_score,
                    "route_count": station.route_count,
                    "avg_delay": station.avg_delay_minutes,
                    "cancellation_rate": station.cancellation_rate,
                    "peak_hours": station.peak_hours or []
                }
                self._set_cache(cache_key, result)
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get station knowledge: {e}")
            return None
    
    def get_route_knowledge(self, source: str, destination: str) -> Optional[Dict]:
        """Get knowledge about a route."""
        cache_key = f"route_knowledge:{source}:{destination}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            from database.algorithm_models import RouteKnowledge
            
            db = self._db()
            route = db.query(RouteKnowledge).filter(
                and_(
                    RouteKnowledge.source_code == source,
                    RouteKnowledge.destination_code == destination
                )
            ).first()
            
            if route:
                result = {
                    "source": route.source_code,
                    "destination": route.destination_code,
                    "duration": route.duration_minutes,
                    "reliability": route.reliability_score,
                    "avg_delay": route.avg_delay_minutes,
                    "on_time_pct": route.on_time_percentage,
                    "searches": route.search_count,
                    "bookings": route.booking_count,
                    "conversion": route.conversion_rate,
                    "avg_fare": route.avg_fare
                }
                self._set_cache(cache_key, result)
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get route knowledge: {e}")
            return None
    
    def get_user_preferences(self, user_id: str) -> Dict:
        """Get learned user preferences."""
        cache_key = f"user_prefs:{user_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            from database.algorithm_models import UserTravelPreference
            
            db = self._db()
            pref = db.query(UserTravelPreference).filter(
                UserTravelPreference.user_id == user_id
            ).first()
            
            if pref:
                result = {
                    "preferred_sources": pref.preferred_sources or [],
                    "preferred_destinations": pref.preferred_destinations or [],
                    "preferred_routes": pref.preferred_routes or [],
                    "preferred_hours": pref.preferred_departure_hours or [],
                    "preferred_class": pref.preferred_class,
                    "class_flexibility": pref.class_flexibility,
                    "avg_advance_days": pref.avg_booking_advance_days,
                    "price_sensitivity": pref.price_sensitivity,
                    "confidence": pref.preference_confidence
                }
                self._set_cache(cache_key, result)
                return result
            
            # Return defaults for new users
            return {
                "preferred_sources": [],
                "preferred_destinations": [],
                "preferred_routes": [],
                "preferred_hours": [],
                "preferred_class": "SL",
                "class_flexibility": 0.5,
                "avg_advance_days": 7,
                "price_sensitivity": 0.5,
                "confidence": 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            return {}
    
    def update_user_preferences(self, user_id: str, booking_data: Dict):
        """Update user preferences from booking data."""
        try:
            from database.algorithm_models import update_user_preference_from_booking
            
            update_user_preference_from_booking(self._db(), user_id, booking_data)
            
            # Invalidate cache
            cache_key = f"user_prefs:{user_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]
                
        except Exception as e:
            logger.error(f"Failed to update user preferences: {e}")
    
    # =========================================================================
    # DEMAND & PRICING OPERATIONS
    # =========================================================================
    
    def record_search_event(self, source: str, destination: str, travel_date: date):
        """Record search event for demand tracking."""
        db: Optional[Session] = None
        try:
            from database.algorithm_models import RouteKnowledge
            
            db = self._db()
            # Update or create route knowledge
            route = db.query(RouteKnowledge).filter(
                and_(
                    RouteKnowledge.source_code == source,
                    RouteKnowledge.destination_code == destination
                )
            ).first()
            
            if route:
                route_any = cast(Any, route)
                route_any.search_count = (route_any.search_count or 0) + 1
                # Update conversion rate
                if route_any.search_count > 0:
                    route_any.conversion_rate = (route_any.booking_count or 0) / route_any.search_count
            else:
                route = RouteKnowledge(
                    source_code=source,
                    destination_code=destination,
                    search_count=1,
                    duration_minutes=0  # Will be updated later
                )
                db.add(route)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record search event: {e}")
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
    
    def record_booking_event(self, source: str, destination: str, 
                             travel_date: date, fare: float):
        """Record booking event for demand tracking."""
        db: Optional[Session] = None
        try:
            from database.algorithm_models import RouteKnowledge, PriceHistory
            from datetime import datetime
            
            db = self._db()
            # Update route knowledge
            route = db.query(RouteKnowledge).filter(
                and_(
                    RouteKnowledge.source_code == source,
                    RouteKnowledge.destination_code == destination
                )
            ).first()
            
            if route:
                route_any = cast(Any, route)
                route_any.booking_count = (route_any.booking_count or 0) + 1
                # Update average fare
                if route_any.booking_count == 1:
                    route_any.avg_fare = fare
                else:
                    route_any.avg_fare = (route_any.avg_fare * (route_any.booking_count - 1) + fare) / route_any.booking_count
                # Update conversion rate
                if route_any.search_count and route_any.search_count > 0:
                    route_any.conversion_rate = route_any.booking_count / route_any.search_count
            
            # Record price history
            days_ahead = (travel_date - date.today()).days if travel_date else 0
            price_record = PriceHistory(
                source_code=source,
                destination_code=destination,
                train_class="SL",  # Default, would be from booking
                travel_date=travel_date,
                days_to_departure=days_ahead,
                day_of_week=travel_date.weekday() if travel_date else 0,
                base_fare=fare,
                final_fare=fare,
                recorded_at=datetime.utcnow()
            )
            db.add(price_record)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record booking event: {e}")
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
    
    def get_demand_snapshot(self, source: str, destination: str, 
                            travel_date: date) -> Optional[Dict]:
        """Get current demand snapshot for a route."""
        try:
            from database.algorithm_models import DemandSnapshot
            
            # Get most recent snapshot
            db = self._db()
            snapshot = db.query(DemandSnapshot).filter(
                and_(
                    DemandSnapshot.source_code == source,
                    DemandSnapshot.destination_code == destination,
                    DemandSnapshot.travel_date == travel_date
                )
            ).order_by(DemandSnapshot.snapshot_time.desc()).first()
            
            if snapshot:
                return {
                    "searches": snapshot.search_count,
                    "bookings": snapshot.booking_count,
                    "demand_score": snapshot.demand_score,
                    "occupancy": snapshot.occupancy_rate,
                    "available_seats": snapshot.available_seats,
                    "recorded_at": snapshot.snapshot_time
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get demand snapshot: {e}")
            return None
    
    def get_historical_demand(self, source: str, destination: str,
                              days_back: int = 30) -> List[Dict]:
        """Get historical demand data for analysis."""
        try:
            from database.algorithm_models import DemandSnapshot
            
            cutoff_date = date.today() - timedelta(days=days_back)
            
            db = self._db()
            snapshots = db.query(DemandSnapshot).filter(
                and_(
                    DemandSnapshot.source_code == source,
                    DemandSnapshot.destination_code == destination,
                    DemandSnapshot.travel_date >= cutoff_date
                )
            ).order_by(DemandSnapshot.travel_date).all()
            
            return [
                {
                    "date": s.travel_date,
                    "searches": s.search_count,
                    "bookings": s.booking_count,
                    "demand_score": s.demand_score,
                    "occupancy": s.occupancy_rate
                }
                for s in snapshots
            ]
            
        except Exception as e:
            logger.error(f"Failed to get historical demand: {e}")
            return []
    
    # =========================================================================
    # PREDICTION OPERATIONS
    # =========================================================================
    
    def record_delay_prediction(self, train_number: str, travel_date: date,
                                predicted_delay: float, confidence: float):
        """Record delay prediction for training data."""
        try:
            from database.algorithm_models import DelayPrediction
            
            db = self._db()
            prediction = DelayPrediction(
                train_number=train_number,
                travel_date=travel_date,
                predicted_delay_minutes=predicted_delay,
                confidence_score=confidence,
                delay_category=self._categorize_delay(predicted_delay)
            )
            db.add(prediction)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record delay prediction: {e}")
    
    def update_actual_delay(self, train_number: str, travel_date: date,
                           actual_delay: float):
        """Update with actual delay for model training."""
        try:
            from database.algorithm_models import DelayPrediction
            
            db = self._db()
            prediction = db.query(DelayPrediction).filter(
                and_(
                    DelayPrediction.train_number == train_number,
                    DelayPrediction.travel_date == travel_date
                )
            ).first()
            
            if prediction:
                prediction_any = cast(Any, prediction)
                prediction_any.actual_delay_minutes = actual_delay
                prediction_any.prediction_error = abs(actual_delay - prediction_any.predicted_delay_minutes)
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update actual delay: {e}")
    
    def _categorize_delay(self, delay_minutes: float) -> str:
        """Categorize delay severity."""
        if delay_minutes <= 5:
            return "on_time"
        elif delay_minutes <= 30:
            return "minor_delay"
        elif delay_minutes <= 120:
            return "major_delay"
        else:
            return "cancelled"
    
    # =========================================================================
    # SEAT ALLOCATION OPERATIONS
    # =========================================================================
    
    def log_seat_allocation(self, booking_id: str, passenger_id: str,
                           train_number: str, coach_id: str, seat_number: str,
                           preference_match: float, allocation_method: str):
        """Log seat allocation decision."""
        try:
            from database.algorithm_models import SeatAllocationLog
            
            log = SeatAllocationLog(
                booking_id=booking_id,
                passenger_id=passenger_id,
                train_number=train_number,
                coach_id=coach_id,
                seat_number=seat_number,
                preference_match_score=preference_match,
                allocation_method=allocation_method
            )
            db = self._db()
            db.add(log)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log seat allocation: {e}")
    
    def get_allocation_stats(self, train_number: str, travel_date: date) -> Dict:
        """Get seat allocation statistics for a train."""
        try:
            from database.algorithm_models import SeatAllocationLog
            from database.models import Booking
            
            # Get bookings for this train
            db = self._db()
            bookings = db.query(Booking).filter(
                and_(
                    Booking.train_number == train_number,
                    Booking.travel_date == travel_date,
                    Booking.booking_status == "confirmed"
                )
            ).count()
            
            # Get allocation logs
            allocations = db.query(SeatAllocationLog).filter(
                SeatAllocationLog.train_number == train_number
            ).all()
            
            if not allocations:
                return {
                    "total_bookings": bookings,
                    "avg_preference_match": 0.0,
                    "method_breakdown": {}
                }
            
            # Calculate stats
            total_match = sum(a.preference_match_score for a in allocations)
            methods = defaultdict(int)
            for a in allocations:
                methods[a.allocation_method] += 1
            
            return {
                "total_bookings": bookings,
                "avg_preference_match": total_match / len(allocations) if allocations else 0,
                "method_breakdown": dict(methods),
                "total_allocated": len(allocations)
            }
            
        except Exception as e:
            logger.error(f"Failed to get allocation stats: {e}")
            return {}
    
    # =========================================================================
    # PERFORMANCE METRICS
    # =========================================================================
    
    def record_algorithm_performance(self, algorithm_name: str, 
                                     request_type: str,
                                     execution_time_ms: float,
                                     success: bool,
                                     results_count: int = 0,
                                     error: Optional[str] = None):
        """Record algorithm performance metrics."""
        try:
            from database.algorithm_models import AlgorithmPerformanceMetric
            
            metric = AlgorithmPerformanceMetric(
                algorithm_name=algorithm_name,
                request_type=request_type,
                execution_time_ms=execution_time_ms,
                success=success,
                results_count=results_count,
                error_message=error
            )
            db = self._db()
            db.add(metric)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record performance: {e}")
    
    def get_algorithm_stats(self, algorithm_name: str, 
                           hours_back: int = 24) -> Dict:
        """Get algorithm performance statistics."""
        try:
            from database.algorithm_models import AlgorithmPerformanceMetric
            
            cutoff = datetime.utcnow() - timedelta(hours=hours_back)
            
            db = self._db()
            metrics = db.query(AlgorithmPerformanceMetric).filter(
                and_(
                    AlgorithmPerformanceMetric.algorithm_name == algorithm_name,
                    AlgorithmPerformanceMetric.recorded_at >= cutoff
                )
            ).all()
            
            if not metrics:
                return {
                    "total_requests": 0,
                    "success_rate": 0.0,
                    "avg_time_ms": 0.0
                }
            
            total = len(metrics)
            successful = sum(1 for m in metrics if cast(Any, m).success)
            times = [m.execution_time_ms for m in metrics]
            
            return {
                "total_requests": total,
                "success_rate": successful / total if total > 0 else 0,
                "avg_time_ms": sum(times) / len(times) if times else 0,
                "min_time_ms": min(times) if times else 0,
                "max_time_ms": max(times) if times else 0,
                "cache_hits": sum(1 for m in metrics if cast(Any, m).cache_hit)
            }
            
        except Exception as e:
            logger.error(f"Failed to get algorithm stats: {e}")
            return {}
    
    # =========================================================================
    # BATCH OPERATIONS (Optimized for API efficiency)
    # =========================================================================
    
    def batch_record_searches(self, searches: List[Dict]):
        """Batch record multiple search events efficiently."""
        db = self._db()
        try:
            from database.algorithm_models import RouteKnowledge
            
            # Group by route
            route_counts = defaultdict(int)
            for s in searches:
                key = (s['source'], s['destination'])
                route_counts[key] += 1
            
            # Update in batch
            for (source, dest), count in route_counts.items():
                db = self._db()
                route = db.query(RouteKnowledge).filter(
                    and_(
                        RouteKnowledge.source_code == source,
                        RouteKnowledge.destination_code == dest
                    )
                ).first()
                
                if route:
                    route_any = cast(Any, route)
                    route_any.search_count = (route_any.search_count or 0) + count
                else:
                    route = RouteKnowledge(
                        source_code=source,
                        destination_code=dest,
                        search_count=count
                    )
                    db.add(route)
            
            db.commit()
            logger.info(f"Batch recorded {len(searches)} searches across {len(route_counts)} routes")
            
        except Exception as e:
            logger.error(f"Failed to batch record searches: {e}")
            try: db.rollback()
            except: pass
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old data to save memory."""
        db = self._db()
        try:
            from database.algorithm_models import (
                DemandSnapshot, PriceHistory, DelayPrediction, 
                CancellationPrediction, AlgorithmPerformanceMetric
            )
            
            cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
            
            db = self._db()
            # Delete old price history
            db.query(PriceHistory).filter(
                PriceHistory.recorded_at < cutoff
            ).delete()
            
            # Delete old performance metrics
            db.query(AlgorithmPerformanceMetric).filter(
                AlgorithmPerformanceMetric.recorded_at < cutoff
            ).delete()
            
            db.commit()
            logger.info(f"Cleaned up data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass


# Global instance
_data_service: Optional[AlgorithmDataService] = None

def get_algorithm_data_service(db: Optional[Session] = None) -> AlgorithmDataService:
    """Get or create global data service instance."""
    global _data_service
    if _data_service is None:
        _data_service = AlgorithmDataService(db)
    elif db is not None:
        _data_service.db = db
    return _data_service
