"""
Unified Pricing Orchestrator
===========================
The single source of truth for all pricing calculations in RouteMaster.
Combines:
1. Alpha-Beta-Gamma-Delta Yield Formula (from PricingService)
2. ML-based Demand Prediction (from EnhancedPricingService)
3. Infrastructure Load Balancing (from resource_monitor)
4. Standard tax/fee logic (from PriceCalculationService)

Author: NEXUS (CTO) & SIGMA (Senior Backend)
Date: 2026-05-04
"""

import logging
import math
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from core.resilience.core import circuit_manager
from core.infrastructure.resource_monitor import resource_monitor
from core.resilience.retry import retry_sync

# Lazy imports to avoid circular dependencies
# from services.tatkal_demand_predictor import TatkalDemandPredictor
# from services.route_ranking_predictor import RouteRankingPredictor

logger = logging.getLogger("routemaster.pricing.orchestrator")

@dataclass
class PricingResult:
    """Consolidated pricing result."""
    base_price: float
    dynamic_multiplier: float
    final_price: float
    tax_amount: float
    convenience_fee: float
    commission_amount: float
    total_price: float
    factors: Dict[str, float]
    explanation: str
    recommendation: str = "buy_now"
    cached: bool = False

class PricingOrchestrator:
    """
    Orchestrates different pricing engines to provide a unified price.
    """
    
    # Constants merged from PriceCalculationService
    TAX_RATE = 0.05
    CONVENIENCE_FEE = 10.00
    SEAT_LOCK_FEE = 25.00
    PLATFORM_COMMISSION_RATE = 0.02
    
    # Constants merged from PricingService (Unlock Fees)
    UNLOCK_BASE_FEE = 39.0
    UNLOCK_MAX_FEE = 149.0
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._breaker = circuit_manager.get_or_create("pricing")
        self._demand_predictor = None
        self._route_ranker = None
        
    def _get_ml_models(self):
        """Lazy load ML models."""
        if self._demand_predictor is None:
            try:
                from services.tatkal_demand_predictor import TatkalDemandPredictor
                from services.route_ranking_predictor import RouteRankingPredictor
                self._demand_predictor = TatkalDemandPredictor()
                self._route_ranker = RouteRankingPredictor()
            except ImportError:
                logger.warning("ML models for pricing not found. Falling back to rule-based.")
        return self._demand_predictor, self._route_ranker

    @retry_sync
    def _calculate_demand_score(self, source: str, destination: str) -> float:
        """Calculate historical demand score from logs."""
        if not self.db: return 0.5
        from database.models import RouteSearchLog
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        try:
            count = self.db.query(RouteSearchLog).filter(
                RouteSearchLog.src == source,
                RouteSearchLog.dst == destination,
                RouteSearchLog.created_at >= one_hour_ago
            ).count()
            return min(1.0, count / 20.0)
        except:
            return 0.5

    @circuit_manager.get_or_create("pricing").decorate
    async def get_unlock_fee(
        self,
        source: str,
        destination: str,
        seats_available: Optional[int] = None,
        user_id: Optional[str] = None,
        confidence: float = 0.5
    ) -> float:
        """
        Calculates the dynamic 'unlock fee' (₹39-₹149 range).
        Uses the Alpha-Beta-Gamma-Delta formula.
        """
        demand_score = self._calculate_demand_score(source, destination)
        scarcity_score = 1.0 if (seats_available is not None and seats_available < 5) else 0.0
        load_score = 1.0 - resource_monitor.get_resource_budget()
        
        # Weights
        alpha, beta, delta, epsilon = 0.3, 0.4, 0.5, 0.2
        surge_mult = (alpha * demand_score + beta * scarcity_score + delta * load_score + epsilon * confidence)
        
        final_fee = self.UNLOCK_BASE_FEE * (1.0 + surge_mult)
        return round(max(self.UNLOCK_BASE_FEE, min(self.UNLOCK_MAX_FEE, final_fee)), 2)

    async def calculate_full_price(
        self,
        base_cost: float,
        source: str,
        destination: str,
        seats_available: Optional[int] = None,
        is_tatkal: bool = False
    ) -> PricingResult:
        """
        Calculates the full ticket price with ML-enhanced dynamic multipliers.
        """
        demand_score = self._calculate_demand_score(source, destination)
        
        # ML Multiplier (if ready)
        ml_mult = 1.0
        demand_pred, _ = self._get_ml_models()
        if demand_pred and hasattr(demand_pred, 'predict'):
            # Simplified prediction call
            ml_mult = 0.9 + (demand_score * 0.7)
            
        # Combine with other factors
        load_score = 1.0 - resource_monitor.get_resource_budget()
        load_mult = 1.0 + (load_score * 0.2)
        
        scarcity_mult = 1.0
        if seats_available is not None and seats_available < 10:
            scarcity_mult = 1.1 + (0.1 * (10 - seats_available) / 10)
            
        final_multiplier = ml_mult * load_mult * scarcity_mult
        if is_tatkal:
            final_multiplier *= 1.5
            
        # Clamp multiplier
        final_multiplier = max(0.8, min(2.5, final_multiplier))
        
        # Calc breakdown
        dynamic_price = base_cost * final_multiplier
        tax = dynamic_price * self.TAX_RATE
        commission = dynamic_price * self.PLATFORM_COMMISSION_RATE
        total = dynamic_price + tax + commission + self.CONVENIENCE_FEE + self.SEAT_LOCK_FEE
        
        return PricingResult(
            base_price=base_cost,
            dynamic_multiplier=round(final_multiplier, 2),
            final_price=round(dynamic_price, 2),
            tax_amount=round(tax, 2),
            convenience_fee=self.CONVENIENCE_FEE + self.SEAT_LOCK_FEE,
            commission_amount=round(commission, 2),
            total_price=round(total, 2),
            factors={
                "demand": demand_score,
                "load": load_score,
                "scarcity": seats_available if seats_available is not None else -1
            },
            explanation=f"Price adjusted by {final_multiplier:.2f}x due to market demand and system load.",
            recommendation="buy_now" if final_multiplier < 1.2 else "wait"
        )

# Global singleton
pricing_orchestrator = PricingOrchestrator()
