"""
💰 DYNAMIC PRICING ENGINE — Patent-Level Revenue Optimization
Implements:
  1. Demand-Supply Curve Pricing (elastic pricing based on fill rate)
  2. Time-Decay Surge (price increases as departure approaches)
  3. Competitor-Aware Pricing (bus/flight price anchoring)
  4. Yield Management (maximize revenue per seat-km)
  5. Fare Bands with Guardrails (min/max caps, regulatory compliance)
  6. Tatkal/Premium Tatkal Dynamic Premiums
"""

import logging
import math
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =========================================================================
# CONFIGURATION & MODELS
# =========================================================================

class PricingStrategy(Enum):
    STATIC = "STATIC"               # Fixed IRCTC slab pricing
    DEMAND_CURVE = "DEMAND_CURVE"   # Elastic demand-based
    TIME_DECAY = "TIME_DECAY"       # Urgency-based surge
    YIELD_MAX = "YIELD_MAX"         # Revenue per seat-km optimization
    COMPETITIVE = "COMPETITIVE"     # Anchored to bus/flight prices


class FareType(Enum):
    GENERAL = "GENERAL"
    TATKAL = "TATKAL"
    PREMIUM_TATKAL = "PREMIUM_TATKAL"
    DYNAMIC = "DYNAMIC"
    PROMOTIONAL = "PROMOTIONAL"


@dataclass(slots=True)
class PricingConfig:
    """Guardrails and configuration for dynamic pricing."""
    # Regulatory caps (% of base fare)
    max_surge_multiplier: float = 1.5       # Max 50% above base
    min_discount_multiplier: float = 0.7    # Max 30% below base
    # Tatkal premiums (IRCTC standard)
    tatkal_premium_pct: Dict[str, float] = field(default_factory=lambda: {
        "SL": 0.30, "3A": 0.30, "2A": 0.30, "1A": 0.30,
        "CC": 0.25, "2S": 0.15, "FC": 0.20,
    })
    premium_tatkal_multiplier: float = 1.75
    # Time-decay parameters
    urgency_start_days: int = 7             # Surge starts 7 days before
    urgency_peak_days: int = 1              # Maximum surge 1 day before
    # Yield optimization
    target_load_factor: float = 0.85        # Optimal fill rate
    revenue_weight: float = 0.6             # vs passenger volume weight
    # Competitive anchoring
    bus_anchor_discount: float = 0.15       # 15% below bus for same route
    flight_anchor_ratio: float = 0.35       # Train should be ~35% of flight


@dataclass(slots=True)
class PricingResult:
    """Output of the pricing engine for a segment."""
    base_fare: float
    dynamic_fare: float
    fare_type: FareType
    strategy_used: PricingStrategy
    surge_multiplier: float
    components: Dict[str, float]     # Breakdown of price components
    savings_vs_static: float         # Positive = user saves, negative = premium
    confidence: float
    reasoning: str
    guardrail_applied: bool = False


@dataclass(slots=True)
class CompetitorPrice:
    """External price data for competitive anchoring."""
    mode: str                # BUS, FLIGHT
    operator: str
    price: float
    duration_minutes: int
    fetched_at: datetime = field(default_factory=datetime.utcnow)


# =========================================================================
# DEMAND-SUPPLY CURVE
# =========================================================================

class DemandSupplyCurve:
    """
    Implements elastic pricing based on supply-demand equilibrium.
    Uses a modified sigmoid to transition smoothly from discount to surge.
    
    Price Multiplier = 1 + k * sigmoid(fill_rate - threshold)
    Where k controls the amplitude and threshold is the inflection point.
    """

    @staticmethod
    def calculate_multiplier(
        fill_rate: float,
        elasticity: float = 2.5,
        threshold: float = 0.7,
        amplitude: float = 0.4
    ) -> float:
        """
        Returns a price multiplier based on fill rate.
        fill_rate < threshold → discount (multiplier < 1.0)
        fill_rate > threshold → surge (multiplier > 1.0)
        """
        x = (fill_rate - threshold) * elasticity
        sigmoid = 1.0 / (1.0 + math.exp(-x))
        # Map sigmoid [0, 1] to multiplier [1 - amplitude, 1 + amplitude]
        multiplier = 1.0 + (2.0 * sigmoid - 1.0) * amplitude
        return round(multiplier, 4)

    @staticmethod
    def calculate_class_elasticity(class_code: str) -> float:
        """Different classes have different price sensitivity."""
        elasticities = {
            "SL": 3.0,   # Highly elastic (budget travelers)
            "3A": 2.5,
            "2A": 2.0,
            "1A": 1.2,   # Inelastic (premium travelers)
            "CC": 2.0,
            "2S": 3.5,   # Most elastic
            "FC": 1.0,   # Least elastic
        }
        return elasticities.get(class_code, 2.5)


# =========================================================================
# TIME-DECAY SURGE
# =========================================================================

class TimeDecaySurge:
    """
    Models urgency-based pricing as departure approaches.
    Uses exponential decay curve calibrated to Indian booking patterns.
    """

    @staticmethod
    def calculate_surge(
        days_until_travel: int,
        base_fill_rate: float,
        config: PricingConfig
    ) -> float:
        """
        Returns an urgency multiplier (1.0 = no surge, >1.0 = surge).
        Surge activates only when fill_rate > 0.5 AND within urgency window.
        """
        if days_until_travel > config.urgency_start_days:
            return 1.0
        if base_fill_rate < 0.5:
            return 1.0  # No surge on empty trains

        # Exponential urgency curve
        # At urgency_start_days: multiplier = 1.0
        # At urgency_peak_days:  multiplier = up to 1.3
        t = max(0, days_until_travel - config.urgency_peak_days)
        t_max = config.urgency_start_days - config.urgency_peak_days
        if t_max <= 0:
            return 1.0
        
        decay = math.exp(-3.0 * t / t_max)
        # Scale by fill rate (higher fill = stronger urgency)
        intensity = min(1.0, base_fill_rate / config.target_load_factor)
        surge = 1.0 + (0.3 * decay * intensity)
        return round(surge, 4)


# =========================================================================
# YIELD OPTIMIZER
# =========================================================================

class YieldOptimizer:
    """
    Optimizes revenue per seat-kilometer.
    Implements a simplified bid-price control mechanism.
    """

    @staticmethod
    def calculate_optimal_price(
        base_fare: float,
        distance_km: float,
        fill_rate: float,
        remaining_capacity: int,
        expected_future_demand: float,
        config: PricingConfig
    ) -> Tuple[float, str]:
        """
        Returns (optimal_price, reasoning).
        Uses marginal seat revenue concept.
        """
        if distance_km <= 0:
            distance_km = 100.0  # Safe default
        
        revenue_per_seat_km = base_fare / distance_km if distance_km > 0 else 1.0

        # If expected future demand > remaining capacity, raise prices
        # (Protect seats for higher-value later bookings)
        if remaining_capacity > 0 and expected_future_demand > remaining_capacity:
            scarcity_ratio = expected_future_demand / remaining_capacity
            protection_premium = min(0.4, (scarcity_ratio - 1.0) * 0.2)
            optimal = base_fare * (1.0 + protection_premium)
            reason = f"Seat protection: {remaining_capacity} seats, {expected_future_demand:.0f} expected demand"
        elif fill_rate < 0.3:
            # Stimulate demand with discount
            discount = min(0.25, (0.3 - fill_rate) * 0.5)
            optimal = base_fare * (1.0 - discount)
            reason = f"Demand stimulation: {fill_rate:.0%} fill rate"
        else:
            optimal = base_fare
            reason = "Equilibrium pricing"

        return round(optimal, 2), reason


# =========================================================================
# COMPETITIVE PRICING
# =========================================================================

class CompetitivePricer:
    """
    Anchors train pricing relative to bus/flight alternatives.
    Ensures trains remain attractive vs competitors.
    """

    @staticmethod
    def anchor_price(
        base_fare: float,
        competitors: List[CompetitorPrice],
        duration_minutes: int,
        config: PricingConfig
    ) -> Tuple[float, str]:
        """
        Adjusts fare based on competitive landscape.
        """
        if not competitors:
            return base_fare, "No competitor data"

        bus_prices = [c.price for c in competitors if c.mode == "BUS"]
        flight_prices = [c.price for c in competitors if c.mode == "FLIGHT"]

        anchored = base_fare
        reason_parts = []

        # Bus anchoring: train should be cheaper than bus for same comfort
        if bus_prices:
            avg_bus = sum(bus_prices) / len(bus_prices)
            target = avg_bus * (1.0 - config.bus_anchor_discount)
            if base_fare > target:
                anchored = min(anchored, target)
                reason_parts.append(f"Bus anchor: ₹{avg_bus:.0f} avg → target ₹{target:.0f}")

        # Flight anchoring: train should be ~35% of flight price
        if flight_prices:
            avg_flight = sum(flight_prices) / len(flight_prices)
            target = avg_flight * config.flight_anchor_ratio
            # Only apply if it would increase the fare (floors, not caps)
            if target > base_fare * 0.8:
                anchored = max(anchored, min(base_fare * 1.1, target))
                reason_parts.append(f"Flight anchor: ₹{avg_flight:.0f} avg → floor ₹{target:.0f}")

        reason = "; ".join(reason_parts) if reason_parts else "No adjustment needed"
        return round(anchored, 2), reason


# =========================================================================
# MAIN ENGINE
# =========================================================================

class DynamicPricingEngine:
    """
    Patent-Level Dynamic Pricing Engine.
    Orchestrates multiple pricing strategies and applies guardrails.
    """

    def __init__(self, config: Optional[PricingConfig] = None):
        self.config = config or PricingConfig()
        self.demand_curve = DemandSupplyCurve()
        self.time_surge = TimeDecaySurge()
        self.yield_optimizer = YieldOptimizer()
        self.competitive_pricer = CompetitivePricer()
        self._price_cache: Dict[str, Tuple[PricingResult, float]] = {}
        self._cache_ttl = 120  # 2 minutes

    async def calculate_dynamic_fare(
        self,
        base_fare: float,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: date,
        class_code: str = "SL",
        fill_rate: float = 0.5,
        remaining_capacity: int = 50,
        expected_demand: float = 60.0,
        distance_km: float = 500.0,
        competitors: Optional[List[CompetitorPrice]] = None,
        strategy: PricingStrategy = PricingStrategy.DEMAND_CURVE,
        is_tatkal: bool = False,
    ) -> PricingResult:
        """Calculate dynamic fare using the specified strategy."""

        cache_key = f"{train_number}:{from_station}:{to_station}:{travel_date}:{class_code}:{strategy.value}"
        cached = self._price_cache.get(cache_key)
        if cached and (time.time() - cached[1]) < self._cache_ttl:
            return cached[0]

        days_until = (travel_date - date.today()).days
        components: Dict[str, float] = {"base_fare": base_fare}

        # 1. Tatkal premium (always applied if tatkal)
        tatkal_premium = 0.0
        fare_type = FareType.GENERAL
        if is_tatkal:
            pct = self.config.tatkal_premium_pct.get(class_code, 0.30)
            tatkal_premium = base_fare * pct
            fare_type = FareType.TATKAL
            components["tatkal_premium"] = tatkal_premium

        working_fare = base_fare + tatkal_premium

        # 2. Strategy-specific pricing
        if strategy == PricingStrategy.DEMAND_CURVE:
            elasticity = self.demand_curve.calculate_class_elasticity(class_code)
            mult = self.demand_curve.calculate_multiplier(fill_rate, elasticity)
            working_fare *= mult
            components["demand_multiplier"] = mult
            if fare_type == FareType.GENERAL:
                fare_type = FareType.DYNAMIC
            elif fare_type == FareType.TATKAL:
                fare_type = FareType.PREMIUM_TATKAL

        elif strategy == PricingStrategy.TIME_DECAY:
            surge = self.time_surge.calculate_surge(days_until, fill_rate, self.config)
            working_fare *= surge
            components["urgency_surge"] = surge
            if fare_type == FareType.GENERAL:
                fare_type = FareType.DYNAMIC
            elif fare_type == FareType.TATKAL:
                fare_type = FareType.PREMIUM_TATKAL

        elif strategy == PricingStrategy.YIELD_MAX:
            optimal, reason = self.yield_optimizer.calculate_optimal_price(
                working_fare, distance_km, fill_rate,
                remaining_capacity, expected_demand, self.config
            )
            working_fare = optimal
            components["yield_reason"] = 0.0  # Placeholder for numeric dict
            if fare_type == FareType.GENERAL:
                fare_type = FareType.DYNAMIC
            elif fare_type == FareType.TATKAL:
                fare_type = FareType.PREMIUM_TATKAL

        elif strategy == PricingStrategy.COMPETITIVE:
            anchored, reason = self.competitive_pricer.anchor_price(
                working_fare, competitors or [], 0, self.config
            )
            working_fare = anchored
            if fare_type == FareType.GENERAL:
                fare_type = FareType.DYNAMIC
            elif fare_type == FareType.TATKAL:
                fare_type = FareType.PREMIUM_TATKAL

        # 3. Composite: Blend demand + time for best accuracy
        if strategy == PricingStrategy.DEMAND_CURVE:
            urgency = self.time_surge.calculate_surge(days_until, fill_rate, self.config)
            if urgency > 1.0:
                working_fare *= (1.0 + (urgency - 1.0) * 0.5)  # 50% of urgency on top
                components["urgency_blend"] = urgency

        # 4. Guardrails
        guardrail_applied = False
        max_fare = (base_fare + tatkal_premium) * self.config.max_surge_multiplier
        min_fare = (base_fare + tatkal_premium) * self.config.min_discount_multiplier
        if working_fare > max_fare:
            working_fare = max_fare
            guardrail_applied = True
        elif working_fare < min_fare:
            working_fare = min_fare
            guardrail_applied = True

        # Round to nearest rupee
        working_fare = round(working_fare)

        surge_mult = working_fare / (base_fare + tatkal_premium) if (base_fare + tatkal_premium) > 0 else 1.0
        savings = (base_fare + tatkal_premium) - working_fare

        result = PricingResult(
            base_fare=base_fare, dynamic_fare=working_fare,
            fare_type=fare_type, strategy_used=strategy,
            surge_multiplier=round(surge_mult, 3),
            components=components,
            savings_vs_static=round(savings, 2),
            confidence=0.85 if fill_rate > 0 else 0.5,
            reasoning=f"{fare_type.value} | {strategy.value} | Fill:{fill_rate:.0%} | Days:{days_until} | Surge:{surge_mult:.2f}x",
            guardrail_applied=guardrail_applied
        )

        # Audit Logging
        audit_logger = logging.getLogger("routemaster.audit.pricing")
        audit_logger.info(f"Audit: {train_number} | {from_station}->{to_station} | {class_code} | "
                          f"Base:{base_fare} | Final:{result.dynamic_fare} | Strategy:{strategy.value} | "
                          f"Reasoning:{result.reasoning}")

        # 4. Cache and Return
        if len(self._price_cache) > 10000:
            # Clear 10% oldest if full (simple eviction)
            keys = sorted(self._price_cache.keys(), key=lambda k: self._price_cache[k][1])[:1000]
            for k in keys: del self._price_cache[k]

        self._price_cache[cache_key] = (result, time.time())
        return result

    def calculate_unlock_fee(self, total_dynamic_fare: float, num_segments: int = 1, is_deep_search: bool = False) -> float:
        """[Step 24-25] complexity-based pricing with 10% cap."""
        from core.pricing.fare_calculator import calculate_unlock_fee as base_calc
        
        fee = base_calc(num_segments=num_segments, is_deep_search=is_deep_search)
        
        # Apply 10% cap
        cap = total_dynamic_fare * 0.10
        if fee > cap:
            fee = cap
            
        return round(fee, 2)

    async def price_route(self, route, class_code: str = "SL",
                          demand_forecasts=None, db=None) -> List[PricingResult]:
        """Price all segments in a route using demand forecasts."""
        from services.ml.demand import demand_forecaster
        from core.pricing.fare_calculator import calculate_fare

        results = []
        for i, seg in enumerate(route.segments):
            travel_date = seg.departure_time.date() if hasattr(seg.departure_time, 'date') else date.today()
            base = calculate_fare(getattr(seg, 'distance_km', 500), class_code)

            # Get demand forecast if available
            fill_rate = 0.5
            expected_demand = 60.0
            if demand_forecasts and i < len(demand_forecasts):
                fill_rate = demand_forecasts[i].predicted_fill_rate
                expected_demand = demand_forecasts[i].predicted_demand

            result = await self.calculate_dynamic_fare(
                base_fare=base["base_fare"], train_number=str(seg.train_number),
                from_station=getattr(seg, 'departure_code', ''),
                to_station=getattr(seg, 'arrival_code', ''),
                travel_date=travel_date, class_code=class_code,
                fill_rate=fill_rate, expected_demand=expected_demand,
                distance_km=getattr(seg, 'distance_km', 500),
            )
            results.append(result)
        return results


# Singleton
dynamic_pricing_engine = DynamicPricingEngine()
