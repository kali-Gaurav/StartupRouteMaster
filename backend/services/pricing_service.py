"""
Pricing Service - Neural Surge Pricing & Yield Controller (NSPYC)
With circuit breaker protection, caching, and comprehensive error handling
"""
import logging
import math
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from core.resource_monitor import resource_monitor
from core.resilience import circuit_breaker_manager
from core.retry import retry_sync

logger = logging.getLogger("routemaster.pricing")


@dataclass
class PricingConfig:
    """Configuration for pricing service."""
    base_fee: float = 39.0
    max_fee: float = 149.0
    cache_ttl_seconds: int = 300  # 5 minutes
    demand_window_hours: int = 1
    intent_window_minutes: int = 30
    circuit_failure_threshold: int = 5


@dataclass
class PricingResult:
    """Result of pricing calculation."""
    source: str
    destination: str
    final_fee: float
    base_fee: float
    demand_score: float
    scarcity_score: float
    intent_score: float
    load_score: float
    value_score: float
    surge_multiplier: float
    cached: bool = False
    calculation_time_ms: int = 0


class PricingService:
    """
    [Point 1 & 25] Neural Surge Pricing & Yield Controller (NSPYC).
    A high-scale monetization engine that prices 'Value', not Features.
    With circuit breaker protection and caching.
    """
    
    BASE_FEE = 39.0
    MAX_FEE = 149.0  # Ethical Cap to maintain trust
    
    # Class-level cache and metrics
    _cache: Dict[str, tuple[PricingResult, datetime]] = {}
    _cache_lock = None  # Will be initialized lazily
    _metrics: deque = deque(maxlen=1000)
    
    def __init__(self, config: Optional[PricingConfig] = None):
        self.config = config or PricingConfig()
        self._breaker = circuit_breaker_manager.get_breaker("pricing")
        
    @classmethod
    def _get_cache_key(cls, source: str, destination: str) -> str:
        """Generate cache key for pricing."""
        return f"pricing:{source}:{destination}"
    
    @classmethod
    def _get_cached_result(cls, source: str, destination: str) -> Optional[PricingResult]:
        """Get cached pricing result."""
        cache_key = cls._get_cache_key(source, destination)
        if cache_key in cls._cache:
            result, timestamp = cls._cache[cache_key]
            if datetime.utcnow() - timestamp < timedelta(seconds=PricingConfig().cache_ttl_seconds):
                result.cached = True
                return result
            del cls._cache[cache_key]
        return None
    
    @classmethod
    def _cache_result(cls, source: str, destination: str, result: PricingResult):
        """Cache pricing result."""
        cache_key = cls._get_cache_key(source, destination)
        cls._cache[cache_key] = (result, datetime.utcnow())
    
    @retry_sync
    def _calculate_demand_score(
        cls, 
        db: Session, 
        source: str, 
        destination: str
    ) -> float:
        """Calculate demand score with retry logic."""
        from database.models import RouteSearchLog
        one_hour_ago = datetime.utcnow() - timedelta(hours=cls.config.demand_window_hours)
        
        search_count = db.query(RouteSearchLog).filter(
            RouteSearchLog.src == source,
            RouteSearchLog.dst == destination,
            RouteSearchLog.created_at >= one_hour_ago
        ).count()
        
        return min(2.0, (search_count / 10.0))
    
    @retry_sync
    def _calculate_intent_score(
        cls, 
        db: Session, 
        user_id: str, 
        source: str, 
        destination: str
    ) -> float:
        """Calculate user intent score with retry logic."""
        from database.models import RouteSearchLog
        recent = db.query(RouteSearchLog).filter(
            RouteSearchLog.user_id == user_id,
            RouteSearchLog.src == source,
            RouteSearchLog.dst == destination,
            RouteSearchLog.created_at >= datetime.utcnow() - timedelta(minutes=cls.config.intent_window_minutes)
        ).count()
        
        return min(1.0, recent / 5.0)

    @circuit_breaker_manager.get_breaker("pricing").decorate
    async def get_dynamic_unlock_fee(
        cls, 
        db: Session, 
        source: str, 
        destination: str, 
        seats_available: Optional[int] = None,
        user_id: Optional[str] = None,
        confidence: float = 0.5,
        bypass_cache: bool = False
    ) -> float:
        """
        Implementation of the Alpha-Beta-Gamma-Delta Yield Formula:
        Price = Base * (1 + aD + bS + gU + dL + eV)
        
        Args:
            db: Database session
            source: Source station code
            destination: Destination station code
            seats_available: Number of seats available
            user_id: User ID for intent tracking
            confidence: Confidence score for route value
            bypass_cache: Skip cache and recalculate
            
        Returns:
            Dynamic unlock fee
        """
        start_time = datetime.utcnow()
        
        # Check cache first
        if not bypass_cache:
            cached = cls._get_cached_result(source, destination)
            if cached:
                logger.debug(f"Pricing cache hit for {source}->{destination}")
                return cached.final_fee
        
        # 1. Demand Engine (D) - Volume Surge
        try:
            demand_score = cls._calculate_demand_score(db, source, destination)
        except Exception as e:
            logger.warning(f"Demand score calculation failed: {e}")
            demand_score = 0.0

        # 2. Scarcity Engine (S) - Seat Intelligence
        scarcity_score = 0.0
        if seats_available is not None:
            if seats_available <= 2:
                scarcity_score = 1.0
            elif seats_available <= 10:
                scarcity_score = 0.5
            elif seats_available <= 50:
                scarcity_score = 0.2
        
        # 3. User Intent Engine (U) - Repeat Searches
        intent_score = 0.0
        if user_id:
            try:
                intent_score = cls._calculate_intent_score(db, user_id, source, destination)
            except Exception as e:
                logger.warning(f"Intent score calculation failed: {e}")
                intent_score = 0.0

        # 4. System Load Engine (L) - Infrastructure Pressure
        load_score = 1.0 - resource_monitor.get_resource_budget()
        
        # 5. Route Value Engine (V) - Prediction Confidence
        value_score = confidence

        # --- FINAL YIELD CALCULATION ---
        # Weights (Optimized for Startup Early Phase)
        alpha, beta, gamma, delta, epsilon = 0.3, 0.4, 0.2, 0.5, 0.2
        
        surge_mult = (
            alpha * demand_score + 
            beta * scarcity_score + 
            gamma * intent_score + 
            delta * load_score + 
            epsilon * value_score
        )
        
        final_fee = cls.BASE_FEE * (1.0 + surge_mult)
        
        # Ethics & Trust Clamping
        final_fee = max(cls.BASE_FEE, min(cls.MAX_FEE, final_fee))
        
        calculation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Create result object
        result = PricingResult(
            source=source,
            destination=destination,
            final_fee=round(final_fee, 2),
            base_fee=cls.BASE_FEE,
            demand_score=demand_score,
            scarcity_score=scarcity_score,
            intent_score=intent_score,
            load_score=load_score,
            value_score=value_score,
            surge_multiplier=surge_mult,
            calculation_time_ms=calculation_time_ms
        )
        
        # Cache the result
        cls._cache_result(source, destination, result)
        
        # Record metrics
        cls._metrics.append({
            "timestamp": datetime.utcnow(),
            "source": source,
            "destination": destination,
            "final_fee": final_fee,
            "calculation_time_ms": calculation_time_ms,
            "cached": False
        })
        
        # [Point 25] Intelligence Loop: log to NIS
        try:
            from services.intelligence_service import IntelligenceService
            intel_svc = IntelligenceService(db)
            # await intel_svc.log_pricing_decision(source, destination, final_fee, surge_mult)
        except Exception as e:
            logger.debug(f"NIS logging skipped: {e}")

        logger.info(f"💰 [YIELD] {source}->{destination} | Multipliers: [D:{demand_score:.1f}, S:{scarcity_score:.1f}, L:{load_score:.1f}] | Fee: ₹{final_fee:.2f}")
        return round(final_fee, 2)

    @classmethod
    def get_pricing_reasons(cls, actual_fee: Optional[float]) -> List[str]:
        """User-facing transparency reasons."""
        reasons = []
        if actual_fee is None:
            return reasons
            
        if actual_fee > cls.BASE_FEE * 1.3:
            reasons.append("High Demand Surge 🔥")
        if actual_fee > cls.BASE_FEE * 2.0:
            reasons.append("Extreme Seat Scarcity 🚨")
        if actual_fee > cls.BASE_FEE * 2.5:
             reasons.append("Priority Infrastructure Load ⚡")
        return reasons
    
    @classmethod
    def get_metrics(cls) -> dict:
        """Get pricing service metrics."""
        if not cls._metrics:
            return {"total_calculations": 0, "avg_calculation_time_ms": 0}
        
        total = len(cls._metrics)
        fees = [m["final_fee"] for m in cls._metrics]
        times = [m["calculation_time_ms"] for m in cls._metrics]
        
        return {
            "total_calculations": total,
            "avg_fee": sum(fees) / len(fees) if fees else 0,
            "min_fee": min(fees) if fees else 0,
            "max_fee": max(fees) if fees else 0,
            "avg_calculation_time_ms": sum(times) / len(times) if times else 0,
            "cache_size": len(cls._cache)
        }
    
    @classmethod
    def clear_cache(cls):
        """Clear pricing cache."""
        cls._cache.clear()
        logger.info("Pricing cache cleared")
    
    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": self._breaker.get_state().value,
            "config": {
                "base_fee": self.config.base_fee,
                "max_fee": self.config.max_fee,
                "cache_ttl_seconds": self.config.cache_ttl_seconds
            },
            "metrics": self.get_metrics()
        }
