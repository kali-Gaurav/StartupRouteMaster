"""
Enhanced Dynamic Pricing Service with ML Integration
====================================================

Integrates ML models (TatkalDemandPredictor, RouteRankingPredictor) with pricing logic.

Features:
- Demand-based dynamic pricing
- Occupancy-based surge pricing
- Time-to-departure pricing
- Revenue optimization
- Competitor price awareness (placeholder)

Author: Backend Intelligence System
Date: 2026-02-17
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from database.models import Route, Trip, StopTime, Stop
from services.tatkal_demand_predictor import TatkalDemandPredictor
from services.route_ranking_predictor import RouteRankingPredictor
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class PricingContext:
    """Context for dynamic pricing decision."""
    base_cost: float
    demand_score: float  # 0 to 1
    occupancy_rate: float  # Current occupancy
    time_to_departure_hours: float
    route_popularity: float  # 0 to 1
    user_booking_history: Dict = None
    is_peak_season: bool = False
    is_holiday: bool = False
    competitor_price: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            'base_cost': self.base_cost,
            'demand_score': self.demand_score,
            'occupancy_rate': self.occupancy_rate,
            'time_to_departure_hours': self.time_to_departure_hours,
            'route_popularity': self.route_popularity,
            'is_peak_season': self.is_peak_season,
            'is_holiday': self.is_holiday,
            'competitor_price': self.competitor_price,
        }


@dataclass
class DynamicPricingResult:
    """Result of dynamic pricing calculation."""
    base_cost: float
    dynamic_multiplier: float
    final_price: float
    tax_amount: float
    convenience_fee: float
    total_price: float
    pricing_factors: Dict[str, float]
    explanation: str
    recommendation: str  # "buy_now", "wait", "premium"


class DynamicPricingEngine:
    """
    ML-powered dynamic pricing engine that optimizes revenue
    while maintaining customer satisfaction.
    
    Architecture:
    1. Demand Prediction: Predict sellout probability
    2. Occupancy Analysis: Current seat availability
    3. Time-Based Pricing: Closer to departure = higher price
    4. Revenue Optimization: ML suggests optimal price
    5. Constraints: Min/max price bounds
    """
    
    # Pricing boundaries
    MIN_PRICE_MULTIPLIER = 0.8  # 20% discount
    MAX_PRICE_MULTIPLIER = 2.5  # 150% premium
    BASE_TAX_RATE = 0.05
    BASE_CONVENIENCE_FEE = 10.0
    
    # Tatkal surge multipliers
    TATKAL_SURGE_MULTIPLIER = 1.5  # 50% premium for Tatkal
    
    def __init__(self):
        """Initialize pricing engine with ML models."""
        self.demand_predictor = TatkalDemandPredictor()
        self.route_ranker = RouteRankingPredictor()
        self.is_ready = False
        
        try:
            self.demand_predictor.load_model()
            self.route_ranker.load_model()
            self.is_ready = True
            logger.info("Dynamic pricing engine initialized with ML models")
        except Exception as e:
            logger.warning(f"ML models not available: {e}. Using fallback pricing.")
            self.is_ready = False
    
    def calculate_dynamic_price(
        self,
        context: PricingContext,
        apply_tatkal_surge: bool = False
    ) -> DynamicPricingResult:
        """
        Calculate dynamic price based on context and ML predictions.
        
        Args:
            context: Pricing context with all relevant factors
            apply_tatkal_surge: Apply 1.5x Tatkal multiplier
        
        Returns:
            DynamicPricingResult with calculated price and explanation
        """
        pricing_factors = {}
        
        # Factor 1: Demand-based multiplier
        demand_multiplier = self._calculate_demand_multiplier(
            context.demand_score,
            context.occupancy_rate,
            context.time_to_departure_hours
        )
        pricing_factors['demand_multiplier'] = demand_multiplier
        
        # Factor 2: Time-to-departure multiplier
        time_multiplier = self._calculate_time_multiplier(
            context.time_to_departure_hours
        )
        pricing_factors['time_multiplier'] = time_multiplier
        
        # Factor 3: Route popularity multiplier
        popularity_multiplier = self._calculate_popularity_multiplier(
            context.route_popularity
        )
        pricing_factors['popularity_multiplier'] = popularity_multiplier
        
        # Factor 4: Seasonality multiplier
        seasonality_multiplier = self._calculate_seasonality_multiplier(
            context.is_peak_season,
            context.is_holiday
        )
        pricing_factors['seasonality_multiplier'] = seasonality_multiplier
        
        # Factor 5: Competitor-aware multiplier
        competitor_multiplier = self._calculate_competitor_multiplier(
            context.base_cost,
            context.competitor_price
        )
        pricing_factors['competitor_multiplier'] = competitor_multiplier
        
        # Combine factors (using geometric mean for stability)
        combined_multiplier = (
            demand_multiplier * 
            time_multiplier * 
            popularity_multiplier * 
            seasonality_multiplier * 
            competitor_multiplier
        ) ** (1 / 5)
        
        # Apply Tatkal surge if applicable
        if apply_tatkal_surge:
            combined_multiplier *= self.TATKAL_SURGE_MULTIPLIER
            pricing_factors['tatkal_surge'] = self.TATKAL_SURGE_MULTIPLIER
        
        # Clamp to bounds
        dynamic_multiplier = np.clip(
            combined_multiplier,
            self.MIN_PRICE_MULTIPLIER,
            self.MAX_PRICE_MULTIPLIER
        )
        pricing_factors['final_multiplier'] = dynamic_multiplier
        
        # Calculate final price with taxes and fees
        cost_before_tax = context.base_cost * dynamic_multiplier
        tax_amount = cost_before_tax * self.BASE_TAX_RATE
        total_before_fee = cost_before_tax + tax_amount
        total_price = total_before_fee + self.BASE_CONVENIENCE_FEE
        
        # Generate explanation
        explanation = self._generate_explanation(
            context, pricing_factors, dynamic_multiplier
        )
        
        # Generate recommendation
        recommendation = self._get_booking_recommendation(
            dynamic_multiplier, context.demand_score
        )
        
        logger.info(
            f"Dynamic pricing: Base={context.base_cost}, "
            f"Multiplier={dynamic_multiplier:.2f}x, "
            f"Final={total_price:.2f}"
        )
        
        return DynamicPricingResult(
            base_cost=context.base_cost,
            dynamic_multiplier=dynamic_multiplier,
            final_price=cost_before_tax,
            tax_amount=tax_amount,
            convenience_fee=self.BASE_CONVENIENCE_FEE,
            total_price=total_price,
            pricing_factors=pricing_factors,
            explanation=explanation,
            recommendation=recommendation
        )
    
    def _calculate_demand_multiplier(
        self,
        demand_score: float,
        occupancy_rate: float,
        hours_to_departure: float
    ) -> float:
        """
        Demand-based pricing: Higher demand & occupancy = higher price.
        
        Uses ML prediction + occupancy for accuracy.
        """
        if not self.is_ready:
            # Fallback: simple occupancy-based
            return 1.0 + (occupancy_rate * 0.5)
        
        # ML-predicted demand score (0 to 1) -> multiplier (0.9 to 1.6)
        # Higher demand means higher multiplier
        demand_multiplier = 0.9 + (demand_score * 0.7)
        
        # Occupancy boost: fuller trains command premium
        occupancy_boost = 0.8 + (occupancy_rate * 0.5)
        
        # Combine
        return demand_multiplier * occupancy_boost
    
    def _calculate_time_multiplier(self, hours_to_departure: float) -> float:
        """
        Time-based pricing: Closer to departure = higher price (last-minute surge).
        
        Bucketing strategy:
        - >14 days: 0.85 (early bird discount)
        - 7-14 days: 0.95 (standard)
        - 1-7 days: 1.10 (soon)
        - <24 hours: 1.40 (last-minute premium)
        """
        if hours_to_departure > 14 * 24:  # >14 days
            return 0.85
        elif hours_to_departure > 7 * 24:  # 7-14 days
            return 0.95
        elif hours_to_departure > 24:  # 1-7 days
            return 1.10
        elif hours_to_departure > 6:  # 6-24 hours
            return 1.25
        else:  # <6 hours (tatkal)
            return 1.40
    
    def _calculate_popularity_multiplier(self, route_popularity: float) -> float:
        """
        Route popularity multiplier based on historical booking patterns.
        
        route_popularity: 0 to 1 score
        Returns: 0.9 to 1.15 multiplier
        """
        return 0.9 + (route_popularity * 0.25)
    
    def _calculate_seasonality_multiplier(
        self,
        is_peak_season: bool,
        is_holiday: bool
    ) -> float:
        """
        Seasonality-based multiplier.
        
        Peak season: 1.20 (20% premium)
        Holiday: 1.35 (35% premium)
        Off-season: 0.90 (10% discount)
        """
        if is_holiday:
            return 1.35
        elif is_peak_season:
            return 1.20
        else:
            return 0.90
    
    def _calculate_competitor_multiplier(
        self,
        our_base_price: float,
        competitor_price: Optional[float]
    ) -> float:
        """
        Competitor-aware pricing to maintain market competitiveness.
        
        If competitor is cheaper, slightly reduce our multiplier.
        If competitor is expensive, take advantage with higher multiplier.
        """
        if competitor_price is None:
            return 1.0
        
        price_ratio = our_base_price / competitor_price if competitor_price > 0 else 1.0
        
        if price_ratio > 1.2:  # We're 20%+ more expensive
            return 0.92  # Reduce our multiplier by 8%
        elif price_ratio < 0.8:  # We're 20%+ cheaper
            return 1.08  # Increase our multiplier by 8%
        else:
            return 1.0  # Neutral
    
    def _generate_explanation(
        self,
        context: PricingContext,
        factors: Dict[str, float],
        multiplier: float
    ) -> str:
        """Generate human-readable explanation of pricing decision."""
        factors_str = []
        
        if factors.get('demand_multiplier', 1.0) > 1.05:
            factors_str.append("high demand")
        
        if factors.get('time_multiplier', 1.0) > 1.1:
            factors_str.append("near departure date")
        elif factors.get('time_multiplier', 1.0) < 0.9:
            factors_str.append("early booking discount")
        
        if context.is_peak_season:
            factors_str.append("peak travel season")
        
        if context.occupancy_rate > 0.8:
            factors_str.append("high occupancy")
        
        if factors_str:
            factors_desc = ", ".join(factors_str)
            return f"Price adjusted ({multiplier:.2f}x) due to {factors_desc}"
        else:
            return f"Price calculated at base rate ({multiplier:.2f}x multiplier)"
    
    def _get_booking_recommendation(
        self,
        multiplier: float,
        demand_score: float
    ) -> str:
        """
        Provide booking recommendation to user.
        
        Returns: "buy_now", "wait", or "premium"
        """
        if multiplier < 0.95:
            return "buy_now"  # Good deal, book now
        elif multiplier > 1.3:
            return "premium"  # Expensive, consider alternatives
        elif demand_score > 0.8:
            return "buy_now"  # High demand, book immediately
        else:
            return "wait"  # Can wait for better deal


class EnhancedPriceCalculationService:
    """
    Enhanced service combining static and dynamic pricing.
    
    Uses DynamicPricingEngine for optimization when available,
    falls back to simple pricing when ML models unavailable.
    """
    
    def __init__(self):
        self.dynamic_engine = DynamicPricingEngine()
        self.base_engine = BasePriceCalculationService()
    
    def calculate_final_price(
        self,
        route: Route,
        user_type: str = "standard",
        use_ml: bool = True
    ) -> Tuple[float, Dict]:
        """
        Calculate final price with optional ML optimization.
        
        Returns: (total_price, price_breakdown)
        """
        if not use_ml or not self.dynamic_engine.is_ready:
            # Fallback to simple pricing
            return self.base_engine.calculate_final_price(route, user_type)
        
        # Build pricing context from route
        context = self._build_pricing_context(route)
        
        # Get dynamic pricing
        result = self.dynamic_engine.calculate_dynamic_price(context)
        
        breakdown = {
            'base_cost': result.base_cost,
            'dynamic_multiplier': result.dynamic_multiplier,
            'dynamic_price': result.final_price,
            'tax_rate': 0.05,
            'tax_amount': result.tax_amount,
            'convenience_fee': result.convenience_fee,
            'final_price': result.total_price,
            'explanation': result.explanation,
            'recommendation': result.recommendation,
            'factors': result.pricing_factors
        }
        
        return result.total_price, breakdown
    
    def _build_pricing_context(self, route: Route) -> PricingContext:
        """Build PricingContext from Route object."""
        # Calculate time to departure
        travel_date = getattr(route, 'travel_date', datetime.now().date())
        now = datetime.now()
        departure_datetime = datetime.combine(travel_date, datetime.min.time())
        hours_to_departure = max(0, (departure_datetime - now).total_seconds() / 3600)
        
        # Placeholder for occupancy (would come from inventory service)
        occupancy_rate = getattr(route, 'occupancy_rate', 0.6)
        
        # Placeholder for demand score (would come from demand predictor)
        demand_score = getattr(route, 'demand_score', 0.5)
        
        # Get competitor price (placeholder)
        competitor_price = getattr(route, 'competitor_price', None)
        
        return PricingContext(
            base_cost=route.total_cost,
            demand_score=demand_score,
            occupancy_rate=occupancy_rate,
            time_to_departure_hours=hours_to_departure,
            route_popularity=getattr(route, 'popularity_score', 0.5),
            is_peak_season=self._is_peak_season(),
            is_holiday=self._is_holiday(),
            competitor_price=competitor_price
        )
    
    @staticmethod
    def _is_peak_season() -> bool:
        """Check if current date is peak season."""
        now = datetime.now()
        month = now.month
        # Peak: Dec-Jan, May-Jun (winter holidays, summer vacations)
        return month in [12, 1, 5, 6]
    
    @staticmethod
    def _is_holiday() -> bool:
        """Check if today is a holiday."""
        # Placeholder: in production, use holiday calendar
        now = datetime.now()
        # Example: Check against holiday dates list
        return False


class BasePriceCalculationService:
    """Simple pricing service - fallback when ML unavailable."""
    
    TAX_RATE = 0.05
    CONVENIENCE_FEE = 10.0
    
    def calculate_final_price(self, route: Route, user_type: str = "standard") -> Tuple[float, Dict]:
        """Calculate price using simple rules."""
        base_cost = route.total_cost
        
        # Apply tax
        cost_after_tax = base_cost * (1 + self.TAX_RATE)
        
        # Apply convenience fee
        final_price = cost_after_tax + self.CONVENIENCE_FEE
        final_price = round(final_price, 2)
        
        breakdown = {
            'base_cost': round(base_cost, 2),
            'tax_rate': self.TAX_RATE,
            'tax_amount': round(base_cost * self.TAX_RATE, 2),
            'convenience_fee': self.CONVENIENCE_FEE,
            'final_price': final_price,
        }
        
        logger.info(f"Base pricing for route {route.id}: {breakdown}")
        
        return final_price, breakdown


# Global instance
enhanced_pricing_service = EnhancedPriceCalculationService()
