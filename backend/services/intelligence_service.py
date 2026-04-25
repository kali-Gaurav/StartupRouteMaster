import logging
import hashlib
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from dataclasses import dataclass
from enum import Enum

from database.models import (
    IntelligenceSearchEvent, IntelligenceRecommendationEvent, ConversionEvent, 
    SafetyEvent, IntelligenceMetric, GlobalIntelligenceState,
    RouteSearchLog
)
from database.models import Base

logger = logging.getLogger("routemaster.intelligence")


class ExperimentVariant(Enum):
    """A/B test variants."""
    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"


class UserSegment(Enum):
    """User segments for personalization."""
    BUDGET = "budget"
    COMFORT = "comfort"
    PREMIUM = "premium"
    FREQUENT = "frequent"
    OCCASIONAL = "occasional"
    NEW = "new"


@dataclass
class IntelligenceConfig:
    """Configuration for intelligence service."""
    cache_ttl_seconds: int = 300
    max_recent_searches: int = 1000
    tuning_interval_minutes: int = 60
    min_samples_for_tuning: int = 100
    anomaly_threshold_std: float = 3.0  # Standard deviations for anomaly detection


# =========================================================================
# PRODUCTION MODELS
# =========================================================================

class ExperimentAssignment(Base):
    """
    A/B test experiment assignments.
    Task: A/B Testing Framework.
    """
    __tablename__ = 'experiment_assignments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    variant = Column(String(20), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assignment_metadata = Column(JSON, nullable=True)


class UserSegmentProfile(Base):
    """
    User segment profiles for personalization.
    Task: User Segmentation.
    """
    __tablename__ = 'user_segment_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    segment = Column(String(20), nullable=False)
    search_count_30d = Column(Integer, default=0)
    avg_fare = Column(Float, default=0)
    conversion_rate = Column(Float, default=0)
    preferred_departure_hour = Column(Integer, nullable=True)
    preferred_days = Column(JSON, nullable=True)  # List of preferred travel days
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(Float, default=0.5)  # Confidence in segment assignment


class DemandForecast(Base):
    """
    Demand forecasting data.
    Task: Demand Forecasting.
    """
    __tablename__ = 'demand_forecasts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_key = Column(String(50), nullable=False, index=True)  # SRC:DST
    forecast_date = Column(DateTime, nullable=False, index=True)
    predicted_searches = Column(Integer, nullable=False)
    predicted_bookings = Column(Integer, nullable=False)
    confidence_score = Column(Float, default=0.0)
    model_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AnomalyEvent(Base):
    """
    Detected anomalies for alerting.
    Task: Anomaly Detection.
    """
    __tablename__ = 'anomaly_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_type = Column(String(50), nullable=False, index=True)  # FRAUD, TRAFFIC, PRICING
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    entity_type = Column(String(30), nullable=True)  # USER, ROUTE, BOOKING
    entity_id = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    metric_name = Column(String(50), nullable=True)
    metric_value = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    deviation = Column(Float, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="open")  # open, investigating, resolved, false_positive


class FeatureStoreEntry(Base):
    """
    Centralized feature definitions.
    Task: Feature Store.
    """
    __tablename__ = 'feature_store'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String(100), unique=True, nullable=False, index=True)
    feature_type = Column(String(30), nullable=False)  # route, user, temporal
    description = Column(Text, nullable=True)
    computation_logic = Column(Text, nullable=False)  # How to compute
    default_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntelligenceService:
    """
    [Point 15 & 25] Nexus Intelligence Store (NIS): The Brain.
    Handles Observation, Intelligence, and Auto-Tuning layers.
    """
    
    def __init__(self, db: Session, config: Optional[IntelligenceConfig] = None):
        self.db = db
        self.config = config or IntelligenceConfig()
        self._cache: Dict[str, Dict] = {}
    
    def _get_cache_key(self, key_type: str, value: str) -> str:
        """Generate cache key for intelligence data."""
        return f"intel:{key_type}:{value}"
    
    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached intelligence data is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self.config.cache_ttl_seconds

    # ==============================================================================
    # 📊 OBSERVATION LAYER: Data Collection
    # ==============================================================================

    async def log_search(self, session_id: str, user_id: Optional[str], src: str, dst: str, persona: str) -> int:
        """
        Capture raw search intent.
        
        Returns:
            The ID of the created search event
        """
        try:
            evt = IntelligenceSearchEvent(
                session_id=session_id, 
                user_id=user_id,
                src=src.upper(), 
                dst=dst.upper(), 
                persona=persona
            )
            self.db.add(evt)
            self.db.commit()
            self.db.refresh(evt)
            
            # Invalidate cache for this route
            cache_key = self._get_cache_key("search_count", f"{src.upper()}:{dst.upper()}")
            self._cache.pop(cache_key, None)
            
            logger.debug(f"📊 Search logged: {session_id} | {src}->{dst}")
            return evt.id
            
        except Exception as e:
            logger.error(f"Failed to log search: {e}")
            self.db.rollback()
            return -1

    async def log_recommendations(self, search_event_id: int, routes: List[Any]):
        """Capture what the system recommended."""
        if not routes:
            return
        
        try:
            for i, r in enumerate(routes):
                try:
                    metadata = r.metadata if hasattr(r, 'metadata') else {}
                    journey_id = getattr(r, 'journey_id', None) or r.get('journey_id')
                    if not journey_id:
                        continue
                        
                    evt = IntelligenceRecommendationEvent(
                        search_event_id=search_event_id,
                        route_id=journey_id,
                        engine=metadata.get("engine", "unknown"),
                        rank=i + 1,
                        value_score=metadata.get("value_score", 0.0),
                        risk_score=metadata.get("risk_score", 1.0),
                        availability_prob=metadata.get("availability_prob", 0.5)
                    )
                    self.db.add(evt)
                except Exception as route_err:
                    logger.warning(f"Failed to log recommendation for route {i}: {route_err}")
            
            self.db.commit()
            logger.debug(f"📊 Logged {len(routes)} recommendations for search {search_event_id}")
            
        except Exception as e:
            logger.error(f"Failed to log recommendations: {e}")
            self.db.rollback()

    async def log_search_served(self, session_id: Optional[str], routes: List[Any]):
        """Link a served search result set back to the original search event."""
        if not session_id:
            return

        try:
            search_event = self.db.query(IntelligenceSearchEvent).filter_by(
                session_id=session_id
            ).order_by(IntelligenceSearchEvent.timestamp.desc()).first()
            
            if not search_event:
                logger.debug(f"No search event found for session {session_id}")
                return

            await self.log_recommendations(search_event.id, routes)
            
        except Exception as e:
            logger.error(f"Failed to log search served: {e}")

    async def record_conversion(self, route_id: str, action: str, revenue: float = 0.0):
        """
        [Conversion Tracking] Understand what actually made money.
        
        Args:
            route_id: The route that was converted
            action: User action (CLICK, UNLOCK, BOOK)
            revenue: Revenue generated from this conversion
        """
        try:
            # Find the latest recommendation for this route
            rec = self.db.query(IntelligenceRecommendationEvent).filter_by(
                route_id=route_id
            ).order_by(IntelligenceRecommendationEvent.timestamp.desc()).first()
            
            if not rec:
                logger.warning(f"No recommendation found for route {route_id}")
                return
            
            evt = ConversionEvent(
                recommendation_event_id=rec.id,
                user_action=action.upper(),
                revenue=revenue
            )
            self.db.add(evt)
            self.db.commit()
            
            # [4.3] Update Route DNA Profile
            await self._update_route_dna_profile(route_id)
            
            logger.info(f"💰 Conversion recorded: {route_id} | {action} | ₹{revenue}")
            
        except Exception as e:
            logger.error(f"Failed to record conversion: {e}")
            self.db.rollback()

    async def log_safety_outcome(self, route_id: str, predicted_risk: float, outcome: str, delay: int = 0):
        """
        [Safety Validation] Validate risk predictions vs reality.
        
        Args:
            route_id: The route that was traveled
            predicted_risk: The risk score that was predicted
            outcome: Actual outcome (SUCCESS, DELAY, SOS)
            delay: Delay in minutes if applicable
        """
        try:
            evt = SafetyEvent(
                route_id=route_id,
                predicted_risk=predicted_risk,
                actual_outcome=outcome.upper(),
                delay_minutes=delay
            )
            self.db.add(evt)
            self.db.commit()
            
            logger.info(f"🛡️ Safety outcome logged: {route_id} | Predicted: {predicted_risk:.2f} | Actual: {outcome}")
            
        except Exception as e:
            logger.error(f"Failed to log safety outcome: {e}")
            self.db.rollback()

    # ==============================================================================
    # 🧠 INTELLIGENCE LAYER: Insight Extraction
    # ==============================================================================

    async def _update_route_dna_profile(self, route_id: str):
        """
        Capture dynamic performance DNA for a specific route.
        """
        try:
            # Calculate conversion rate for this route in last 7 days
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            total_recs = self.db.query(IntelligenceRecommendationEvent).filter(
                IntelligenceRecommendationEvent.route_id == route_id,
                IntelligenceRecommendationEvent.timestamp > week_ago
            ).count()
            
            if total_recs < 10:
                logger.debug(f"Insufficient data to update route DNA for {route_id}")
                return
            
            conversions = self.db.query(ConversionEvent).join(IntelligenceRecommendationEvent).filter(
                IntelligenceRecommendationEvent.route_id == route_id,
                ConversionEvent.user_action == 'UNLOCK',
                ConversionEvent.timestamp > week_ago
            ).count()
            
            cv_rate = conversions / total_recs if total_recs > 0 else 0.0
            
            # Save to IntelligenceMetric
            metric = self.db.query(IntelligenceMetric).filter_by(
                metric_key='route_dna_cv', entity_id=route_id
            ).first()
            
            if not metric:
                metric = IntelligenceMetric(metric_key='route_dna_cv', entity_id=route_id)
                self.db.add(metric)
            
            metric.value = cv_rate
            metric.sample_size = total_recs
            metric.last_updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.debug(f"🧬 Route DNA updated: {route_id} | CV Rate: {cv_rate:.2%} | Samples: {total_recs}")
            
        except Exception as e:
            logger.error(f"Failed to update route DNA: {e}")
            self.db.rollback()

    async def get_route_dna(self, route_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the performance DNA for a specific route.
        
        Returns:
            Dict with route DNA metrics or None if not found
        """
        cache_key = self._get_cache_key("route_dna", route_id)
        
        # Check cache
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            return self._cache[cache_key]
        
        try:
            metric = self.db.query(IntelligenceMetric).filter_by(
                metric_key='route_dna_cv', 
                entity_id=route_id
            ).first()
            
            if not metric:
                return None
            
            result = {
                "route_id": route_id,
                "conversion_rate": metric.value,
                "sample_size": metric.sample_size,
                "last_updated": metric.last_updated_at.isoformat() if metric.last_updated_at else None
            }
            
            # Cache the result
            result["_cached_at"] = datetime.utcnow().timestamp()
            self._cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get route DNA: {e}")
            return None

    async def get_search_volume(self, source: str, destination: str, hours: int = 1) -> int:
        """
        Get the search volume for a route in the last N hours.
        
        Args:
            source: Source station code
            destination: Destination station code
            hours: Number of hours to look back
            
        Returns:
            Number of searches in the time window
        """
        cache_key = self._get_cache_key("search_count", f"{source.upper()}:{destination.upper()}:{hours}")
        
        # Check cache
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            return self._cache[cache_key].get("count", 0)
        
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            count = self.db.query(RouteSearchLog).filter(
                RouteSearchLog.src == source.upper(),
                RouteSearchLog.dst == destination.upper(),
                RouteSearchLog.created_at >= cutoff
            ).count()
            
            # Cache the result
            self._cache[cache_key] = {
                "count": count,
                "_cached_at": datetime.utcnow().timestamp()
            }
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to get search volume: {e}")
            return 0

    # ==============================================================================
    # ⚙️ ACTION LAYER: Auto-Tuning
    # ==============================================================================

    async def tune_global_weights(self) -> Dict[str, Any]:
        """
        [THE BRAIN] Automatically adjust scoring weights based on NIS insights.
        Phase 1: Rule-Based Updates.
        
        Returns:
            Dict with updated weights and tuning info
        """
        logger.info("🧠 [NIS] Initiating Global Intelligence Auto-Tune...")
        
        try:
            state = self.db.query(GlobalIntelligenceState).first()
            if not state:
                state = GlobalIntelligenceState()
                self.db.add(state)
                self.db.commit()

            # Check if we have enough data for tuning
            avg_cv = self.db.query(func.avg(IntelligenceMetric.value)).filter_by(
                metric_key='route_dna_cv'
            ).scalar() or 0.0
            
            total_samples = self.db.query(func.sum(IntelligenceMetric.sample_size)).filter_by(
                metric_key='route_dna_cv'
            ).scalar() or 0
            
            if total_samples < self.config.min_samples_for_tuning:
                logger.info(f"📊 [NIS] Insufficient data for tuning. Samples: {total_samples}")
                return {
                    "tuned": False,
                    "reason": "insufficient_data",
                    "samples": total_samples
                }

            changes = {}
            
            # Insight 1: Conversion vs Availability
            if avg_cv < 0.05:
                logger.warning("📉 [NIS] Low conversion detected. Penalizing Availability weight, Boosting Speed.")
                old_avail = state.w_availability
                old_speed = state.w_speed
                state.w_availability = max(0.1, state.w_availability - 0.05)
                state.w_speed = min(0.6, state.w_speed + 0.05)
                changes["availability"] = {"old": old_avail, "new": state.w_availability}
                changes["speed"] = {"old": old_speed, "new": state.w_speed}
            
            # Insight 2: Safety False Positives
            false_positives = self.db.query(SafetyEvent).filter(
                SafetyEvent.predicted_risk > 0.7,
                SafetyEvent.actual_outcome == 'SUCCESS'
            ).count()
            
            if false_positives > 50:
                logger.info("🛡️ [NIS] System too conservative. Reducing Safety penalty.")
                old_safety = state.w_safety
                state.w_safety = max(0.05, state.w_safety - 0.02)
                changes["safety"] = {"old": old_safety, "new": state.w_safety}
            
            state.version += 1
            state.last_tuned_at = datetime.utcnow()
            self.db.commit()
            
            result = {
                "tuned": True,
                "version": state.version,
                "changes": changes,
                "avg_conversion": avg_cv,
                "total_samples": total_samples
            }
            
            logger.info(f"🚀 [NIS] Global Weights Updated: Ver {state.version} | " +
                       f"Avail: {state.w_availability} | Speed: {state.w_speed} | " +
                       f"Comfort: {state.w_comfort} | Safety: {state.w_safety}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to tune weights: {e}")
            self.db.rollback()
            return {"tuned": False, "error": str(e)}

    @staticmethod
    async def get_current_weights(db: Session) -> Dict[str, float]:
        """Get the current scoring weights."""
        try:
            state = db.query(GlobalIntelligenceState).first()
            if not state:
                return {"availability": 0.4, "speed": 0.3, "comfort": 0.2, "safety": 0.1}
            return {
                "availability": state.w_availability,
                "speed": state.w_speed,
                "comfort": state.w_comfort,
                "safety": state.w_safety
            }
        except Exception as e:
            logger.error(f"Failed to get current weights: {e}")
            return {"availability": 0.4, "speed": 0.3, "comfort": 0.2, "safety": 0.1}

    def clear_cache(self) -> None:
        """Clear intelligence cache."""
        self._cache.clear()
        logger.info("Intelligence cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "ttl_seconds": self.config.cache_ttl_seconds
        }

    # =========================================================================
    # PRODUCTION FEATURES
    # =========================================================================

    # =========================================================================
    # TASK INT-1: A/B TESTING FRAMEWORK
    # =========================================================================

    async def assign_experiment(
        self,
        user_id: str,
        experiment_name: str,
        variants: List[str] = None
    ) -> str:
        """
        Assign user to A/B test variant.
        Uses deterministic hashing for consistent assignment.
        """
        if variants is None:
            variants = ["control", "variant_a", "variant_b"]
        
        # Deterministic assignment based on user_id + experiment
        hash_input = f"{user_id}:{experiment_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        variant_index = hash_value % len(variants)
        variant = variants[variant_index]
        
        try:
            # Check if already assigned
            existing = self.db.query(ExperimentAssignment).filter(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_id == experiment_name
            ).first()
            
            if existing:
                return existing.variant
            
            # Create new assignment
            assignment = ExperimentAssignment(
                experiment_id=experiment_name,
                user_id=user_id,
                variant=variant
            )
            self.db.add(assignment)
            self.db.commit()
            
            logger.info(f"🧪 Assigned user {user_id} to {experiment_name}: {variant}")
            return variant
            
        except Exception as e:
            logger.error(f"Failed to assign experiment: {e}")
            self.db.rollback()
            return variants[0]  # Return control on error

    async def get_experiment_variant(
        self,
        user_id: str,
        experiment_name: str
    ) -> Optional[str]:
        """Get user's assigned variant for an experiment."""
        try:
            assignment = self.db.query(ExperimentAssignment).filter(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_id == experiment_name
            ).first()
            
            return assignment.variant if assignment else None
        except Exception as e:
            logger.error(f"Failed to get experiment variant: {e}")
            return None

    async def log_experiment_outcome(
        self,
        user_id: str,
        experiment_name: str,
        metric_name: str,
        metric_value: float
    ) -> None:
        """Log outcome metrics for A/B test analysis."""
        # In production: store in experiment_results table
        logger.info(f"🧪 Experiment {experiment_name} outcome: {metric_name}={metric_value}")

    # =========================================================================
    # TASK INT-2: USER SEGMENTATION
    # =========================================================================

    async def update_user_segment(self, user_id: str) -> UserSegment:
        """
        Update user segment based on behavior.
        """
        try:
            # Get user statistics
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # Search count
            search_count = self.db.query(IntelligenceSearchEvent).filter(
                IntelligenceSearchEvent.user_id == user_id,
                IntelligenceSearchEvent.timestamp >= thirty_days_ago
            ).count()
            
            # Average fare (from conversions)
            # In production: query actual booking data
            
            # Determine segment
            if search_count == 0:
                segment = UserSegment.NEW
            elif search_count < 5:
                segment = UserSegment.OCCASIONAL
            elif search_count < 20:
                segment = UserSegment.FREQUENT
            else:
                segment = UserSegment.FREQUENT  # Could be BUDGET/COMFORT based on fare
            
            # Update or create profile
            profile = self.db.query(UserSegmentProfile).filter_by(
                user_id=user_id
            ).first()
            
            if not profile:
                profile = UserSegmentProfile(user_id=user_id)
                self.db.add(profile)
            
            profile.segment = segment.value
            profile.search_count_30d = search_count
            profile.last_updated = datetime.utcnow()
            profile.confidence = min(1.0, search_count / 20)  # Higher confidence with more data
            
            self.db.commit()
            
            logger.info(f"👤 User {user_id} segment updated: {segment.value}")
            return segment
            
        except Exception as e:
            logger.error(f"Failed to update user segment: {e}")
            self.db.rollback()
            return UserSegment.NEW

    async def get_user_segment(self, user_id: str) -> Optional[UserSegment]:
        """Get user's current segment."""
        try:
            profile = self.db.query(UserSegmentProfile).filter_by(
                user_id=user_id
            ).first()
            
            if profile:
                return UserSegment(profile.segment)
            return None
        except Exception as e:
            logger.error(f"Failed to get user segment: {e}")
            return None

    def get_personalized_weights(self, user_id: str) -> Dict[str, float]:
        """
        Get personalized scoring weights based on user segment.
        """
        # Default weights
        weights = {
            "availability": 0.4,
            "speed": 0.3,
            "comfort": 0.2,
            "safety": 0.1
        }
        
        # In production: fetch from database based on segment
        # This is a simplified implementation
        
        return weights

    # =========================================================================
    # TASK INT-3: DEMAND FORECASTING
    # =========================================================================

    async def forecast_demand(
        self,
        source: str,
        destination: str,
        date: datetime
    ) -> Optional[Dict]:
        """
        Forecast search/booking demand for a route and date.
        """
        try:
            route_key = f"{source.upper()}:{destination.upper()}"
            
            # Check cache first
            cache_key = f"forecast:{route_key}:{date.date()}"
            if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
                return self._cache[cache_key]
            
            # Get historical data (last 30 days)
            thirty_days_ago = date - timedelta(days=30)
            
            # Query historical searches
            historical_count = self.db.query(RouteSearchLog).filter(
                RouteSearchLog.src == source.upper(),
                RouteSearchLog.dst == destination.upper(),
                RouteSearchLog.created_at >= thirty_days_ago,
                RouteSearchLog.created_at <= date
            ).count()
            
            # Simple forecasting: use rolling average with day-of-week adjustment
            day_of_week = date.weekday()
            
            # Weekend adjustment factor
            weekend_factor = 1.3 if day_of_week >= 5 else 1.0
            
            # Calculate forecast
            daily_avg = historical_count / 30 if historical_count > 0 else 10
            predicted_searches = int(daily_avg * weekend_factor)
            predicted_bookings = int(predicted_searches * 0.15)  # ~15% conversion
            
            # Confidence based on data volume
            confidence = min(0.9, historical_count / 100) if historical_count > 0 else 0.3
            
            result = {
                "route_key": route_key,
                "date": date.date().isoformat(),
                "predicted_searches": predicted_searches,
                "predicted_bookings": predicted_bookings,
                "confidence_score": confidence,
                "historical_searches": historical_count,
                "day_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day_of_week]
            }
            
            # Cache result
            result["_cached_at"] = datetime.utcnow().timestamp()
            self._cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Demand forecast failed: {e}")
            return None

    # =========================================================================
    # TASK INT-4: ANOMALY DETECTION
    # =========================================================================

    async def detect_anomaly(
        self,
        anomaly_type: str,
        entity_type: str,
        entity_id: str,
        metric_name: str,
        current_value: float,
        expected_value: float
    ) -> Optional[AnomalyEvent]:
        """
        Detect anomalies based on statistical thresholds.
        """
        try:
            # Calculate deviation
            if expected_value == 0:
                deviation = abs(current_value) if current_value > 0 else 0
            else:
                deviation = abs((current_value - expected_value) / expected_value)
            
            # Check if exceeds threshold
            if deviation < self.config.anomaly_threshold_std:
                return None  # No anomaly
            
            # Determine severity
            if deviation >= 5:
                severity = "CRITICAL"
            elif deviation >= 4:
                severity = "HIGH"
            elif deviation >= 3:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            # Create anomaly event
            anomaly = AnomalyEvent(
                anomaly_type=anomaly_type,
                severity=severity,
                entity_type=entity_type,
                entity_id=entity_id,
                description=f"{anomaly_type} anomaly detected for {entity_type} {entity_id}",
                metric_name=metric_name,
                metric_value=current_value,
                expected_value=expected_value,
                deviation=deviation
            )
            
            self.db.add(anomaly)
            self.db.commit()
            
            logger.warning(f"🚨 Anomaly detected: {anomaly_type} | {severity} | {entity_id}")
            
            return anomaly
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            self.db.rollback()
            return None

    async def get_active_anomalies(
        self,
        severity: Optional[str] = None,
        anomaly_type: Optional[str] = None
    ) -> List[Dict]:
        """Get active anomalies."""
        try:
            query = self.db.query(AnomalyEvent).filter(
                AnomalyEvent.status == "open"
            )
            
            if severity:
                query = query.filter(AnomalyEvent.severity == severity)
            if anomaly_type:
                query = query.filter(AnomalyEvent.anomaly_type == anomaly_type)
            
            anomalies = query.order_by(AnomalyEvent.detected_at.desc()).limit(100).all()
            
            return [
                {
                    "id": a.id,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "description": a.description,
                    "metric_name": a.metric_name,
                    "metric_value": a.metric_value,
                    "expected_value": a.expected_value,
                    "deviation": a.deviation,
                    "detected_at": a.detected_at.isoformat()
                }
                for a in anomalies
            ]
        except Exception as e:
            logger.error(f"Failed to get anomalies: {e}")
            return []

    async def resolve_anomaly(self, anomaly_id: int, resolution: str) -> bool:
        """Resolve an anomaly."""
        try:
            anomaly = self.db.query(AnomalyEvent).filter(
                AnomalyEvent.id == anomaly_id
            ).first()
            
            if not anomaly:
                return False
            
            anomaly.status = resolution  # resolved, false_positive, investigating
            anomaly.resolved_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"✅ Anomaly {anomaly_id} resolved: {resolution}")
            return True
        except Exception as e:
            logger.error(f"Failed to resolve anomaly: {e}")
            self.db.rollback()
            return False

    # =========================================================================
    # TASK INT-5: FEATURE STORE
    # =========================================================================

    def register_feature(
        self,
        feature_name: str,
        feature_type: str,
        computation_logic: str,
        default_value: Optional[float] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> bool:
        """
        Register a feature in the central store.
        """
        try:
            existing = self.db.query(FeatureStoreEntry).filter_by(
                feature_name=feature_name
            ).first()
            
            if existing:
                # Update existing
                existing.feature_type = feature_type
                existing.computation_logic = computation_logic
                existing.default_value = default_value
                existing.min_value = min_value
                existing.max_value = max_value
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                feature = FeatureStoreEntry(
                    feature_name=feature_name,
                    feature_type=feature_type,
                    description=f"Auto-registered feature: {feature_name}",
                    computation_logic=computation_logic,
                    default_value=default_value,
                    min_value=min_value,
                    max_value=max_value
                )
                self.db.add(feature)
            
            self.db.commit()
            logger.info(f"📦 Feature registered: {feature_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register feature: {e}")
            self.db.rollback()
            return False

    def get_feature_definition(self, feature_name: str) -> Optional[Dict]:
        """Get feature definition from store."""
        try:
            feature = self.db.query(FeatureStoreEntry).filter_by(
                feature_name=feature_name
            ).first()
            
            if not feature:
                return None
            
            return {
                "feature_name": feature.feature_name,
                "feature_type": feature.feature_type,
                "description": feature.description,
                "computation_logic": feature.computation_logic,
                "default_value": feature.default_value,
                "min_value": feature.min_value,
                "max_value": feature.max_value
            }
        except Exception as e:
            logger.error(f"Failed to get feature: {e}")
            return None

    # =========================================================================
    # TASK INT-6: REAL-TIME SCORING
    # =========================================================================

    async def score_route_realtime(
        self,
        route: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Score a route in real-time for ranking.
        """
        try:
            # Get base weights
            if user_id:
                weights = self.get_personalized_weights(user_id)
            else:
                weights = await IntelligenceService.get_current_weights(self.db)
            
            # Calculate component scores
            availability_score = route.get("availability_probability", 0.5)
            speed_score = self._normalize_speed(route.get("duration_minutes", 999))
            comfort_score = route.get("comfort_score", 0.5)
            safety_score = route.get("safety_score", 1.0)
            
            # Calculate weighted total
            total_score = (
                weights["availability"] * availability_score +
                weights["speed"] * speed_score +
                weights["comfort"] * comfort_score +
                weights["safety"] * safety_score
            )
            
            return {
                "route_id": route.get("route_id"),
                "total_score": total_score,
                "component_scores": {
                    "availability": availability_score,
                    "speed": speed_score,
                    "comfort": comfort_score,
                    "safety": safety_score
                },
                "weights_used": weights,
                "scored_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Real-time scoring failed: {e}")
            return {"error": str(e)}

    def _normalize_speed(self, duration_minutes: int) -> float:
        """Normalize speed score (0-1, higher is better)."""
        # Assume 0-600 minutes (10 hours) is the range
        max_duration = 600
        return max(0, 1 - (duration_minutes / max_duration))
