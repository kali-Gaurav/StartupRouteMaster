"""
Yield Management Engine - Revenue Optimization & Inventory Allocation
=====================================================================

Implements IRCTC-inspired yield management strategies:
1. Micro-segment pricing (origin-destination pairs, time windows)
2. Competitive pricing analysis
3. Price elasticity modeling
4. Dynamic quota allocation (General, Tatkal, Ladies, etc.)
5. Overbooking optimization
6. Cancellation prediction and management

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QuotaType(Enum):
    """IRCTC-style quota types."""
    GENERAL = "general"
    TATKAL = "tatkal"
    LADIES = "ladies"
    SENIOR_CITIZEN = "senior_citizen"
    DEFENCE = "defence"
    FOREIGN_TOURIST = "foreign_tourist"


@dataclass
class SegmentRevenue:
    """Revenue metrics for an origin-destination pair."""
    origin_code: str
    destination_code: str
    base_fare: float
    current_price: float
    seats_available: int
    total_seats: int
    booking_velocity: float  # bookings per hour
    demand_forecast: float  # 0-1 probability of full occupancy
    competitor_price: Optional[float] = None
    revenue: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate."""
        return 1 - (self.seats_available / max(self.total_seats, 1))
    
    @property
    def price_elasticity(self) -> float:
        """Simple elasticity: how much demand changes with 1% price increase."""
        return -0.8  # Assumption: -0.8% demand decrease per 1% price increase


@dataclass
class QuotaAllocation:
    """Optimal quota allocation for a train."""
    train_id: int
    travel_date: str
    total_seats: int
    allocations: Dict[QuotaType, int] = field(default_factory=dict)
    revenue_projection: float = 0.0
    
    def __post_init__(self):
        """Initialize with default allocations if empty."""
        if not self.allocations:
            self.allocations = self._default_allocations()
    
    def _default_allocations(self) -> Dict[QuotaType, int]:
        """Default allocation based on IRCTC standards."""
        total = self.total_seats
        return {
            QuotaType.GENERAL: int(total * 0.50),        # 50%
            QuotaType.TATKAL: int(total * 0.10),         # 10%
            QuotaType.LADIES: int(total * 0.15),         # 15%
            QuotaType.SENIOR_CITIZEN: int(total * 0.10), # 10%
            QuotaType.DEFENCE: int(total * 0.05),        # 5%
            QuotaType.FOREIGN_TOURIST: int(total * 0.10), # 10%
        }


@dataclass
class OverbookingStrategy:
    """Overbooking optimization based on cancellation prediction."""
    train_id: int
    quota_type: QuotaType
    predicted_cancellation_rate: float  # 0-1
    overbooking_percentage: float  # How much to overbook
    seats_allocated: int
    seats_overbooked: int = 0
    
    def __post_init__(self):
        """Calculate overbooking seats."""
        max_overbook = self.predicted_cancellation_rate
        self.seats_overbooked = max(
            0,
            int(self.seats_allocated * min(self.overbooking_percentage, max_overbook))
        )


class YieldManagementEngine:
    """
    Core yield management engine for revenue optimization.
    
    Strategies:
    1. Micro-Segment Pricing
    2. Competitive Pricing Analysis  
    3. Dynamic Quota Allocation
    4. Overbooking Optimization
    5. Cancellation Prediction
    """
    
    # Pricing parameters
    BASE_PRICE_MULTIPLIER_RANGE = (0.80, 2.50)  # Min to max
    DEMAND_THRESHOLD_HIGH = 0.7  # High demand threshold
    DEMAND_THRESHOLD_LOW = 0.3   # Low demand threshold
    
    # Occupancy-based pricing
    OCCUPANCY_MULTIPLIERS = {
        0.0: 0.80,   # 0% occupied: 20% discount
        0.25: 0.90,
        0.50: 1.00,  # 50% occupied: base price
        0.75: 1.30,  # 75% occupied: 30% premium
        0.90: 1.80,  # 90% occupied: 80% premium
        1.00: 2.50,  # 100% occupied: 150% premium
    }
    
    # Time-based pricing
    TIME_MULTIPLIERS = {
        # Days to departure -> multiplier
        7: 1.0,      # 7+ days: base price
        5: 1.1,      # 5-7 days: 10% premium
        3: 1.3,      # 3-5 days: 30% premium
        1: 1.8,      # 1-3 days: 80% premium
        0: 2.5,      # <24 hours: 150% premium (last-minute)
    }
    
    def __init__(self):
        """Initialize yield management engine."""
        self.segment_revenues: Dict[Tuple[str, str], SegmentRevenue] = {}
        self.logger = logging.getLogger(__name__)
    
    # ========================================================================
    # 1. MICRO-SEGMENT PRICING
    # ========================================================================
    
    def calculate_segment_price(
        self,
        origin: str,
        destination: str,
        base_fare: float,
        occupancy_rate: float,
        demand_score: float,
        time_to_departure_hours: float,
        competitor_price: Optional[float] = None,
        is_peak_season: bool = False,
        is_holiday: bool = False,
    ) -> Dict:
        """
        Calculate optimal price for an OD (origin-destination) pair.
        
        Factors considered:
        - Current occupancy
        - Demand forecast
        - Time to departure
        - Competitor pricing
        - Seasonality
        """
        segment_key = (origin, destination)
        
        # Start with base fare
        price = base_fare
        factors = {'base': base_fare}
        
        # 1. Occupancy-based multiplier
        occupancy_mult = self._get_occupancy_multiplier(occupancy_rate)
        price *= occupancy_mult
        factors['occupancy'] = occupancy_mult
        
        # 2. Demand-based multiplier
        demand_mult = self._get_demand_multiplier(demand_score)
        price *= demand_mult
        factors['demand'] = demand_mult
        
        # 3. Time-based multiplier (closer to departure = higher price)
        time_mult = self._get_time_multiplier(time_to_departure_hours)
        price *= time_mult
        factors['time_to_departure'] = time_mult
        
        # 4. Competitive pricing adjustment
        if competitor_price:
            competitor_mult = self._get_competitor_multiplier(price, competitor_price)
            price *= competitor_mult
            factors['competitive'] = competitor_mult
        
        # 5. Seasonal multiplier
        if is_peak_season:
            price *= 1.15  # 15% premium
            factors['peak_season'] = 1.15
        
        if is_holiday:
            price *= 1.20  # 20% premium
            factors['holiday'] = 1.20
        
        # Apply bounds
        multiplier = price / base_fare
        multiplier = np.clip(multiplier, *self.BASE_PRICE_MULTIPLIER_RANGE)
        price = base_fare * multiplier
        
        factors['final_multiplier'] = multiplier
        factors['final_price'] = round(price, 2)
        
        # Record segment revenue
        self.segment_revenues[segment_key] = SegmentRevenue(
            origin_code=origin,
            destination_code=destination,
            base_fare=base_fare,
            current_price=price,
            seats_available=0,  # TODO: get from inventory
            total_seats=100,    # TODO: get from train config
            booking_velocity=0.0,  # TODO: get from booking service
            demand_forecast=demand_score,
            competitor_price=competitor_price,
            revenue=price  # Simplified; actual would be price * expected_bookings
        )
        
        return factors
    
    def _get_occupancy_multiplier(self, occupancy_rate: float) -> float:
        """Get price multiplier based on occupancy."""
        # Find closest occupancy level
        levels = sorted(self.OCCUPANCY_MULTIPLIERS.keys())
        for i, level in enumerate(levels):
            if occupancy_rate <= level:
                if i == 0:
                    return self.OCCUPANCY_MULTIPLIERS[level]
                # Linear interpolation between levels
                prev_level = levels[i - 1]
                prev_mult = self.OCCUPANCY_MULTIPLIERS[prev_level]
                curr_mult = self.OCCUPANCY_MULTIPLIERS[level]
                t = (occupancy_rate - prev_level) / (level - prev_level)
                return prev_mult + t * (curr_mult - prev_mult)
        
        return self.OCCUPANCY_MULTIPLIERS[levels[-1]]
    
    def _get_demand_multiplier(self, demand_score: float) -> float:
        """
        Get multiplier based on demand forecast.
        
        demand_score: 0-1, higher = more demand
        """
        if demand_score >= self.DEMAND_THRESHOLD_HIGH:
            return 1.5  # 50% premium for high demand
        elif demand_score >= self.DEMAND_THRESHOLD_LOW:
            return 1.0 + (demand_score - self.DEMAND_THRESHOLD_LOW) * 1.5
        else:
            return 0.85 + demand_score * 0.5  # Up to 10% discount
    
    def _get_time_multiplier(self, time_to_departure_hours: float) -> float:
        """Get multiplier based on time to departure."""
        days_to_departure = time_to_departure_hours / 24
        
        # Find appropriate multiplier
        for days_threshold, mult in sorted(
            self.TIME_MULTIPLIERS.items(), key=lambda x: x[0], reverse=True
        ):
            if days_to_departure >= days_threshold:
                return mult
        
        return self.TIME_MULTIPLIERS[0]  # Minimum
    
    def _get_competitor_multiplier(
        self, our_price: float, competitor_price: float
    ) -> float:
        """
        Adjust our price based on competitor pricing.
        
        Strategy: Stay within 10% of competitor, but don't go below 90% of our base.
        """
        if competitor_price == 0:
            return 1.0
        
        price_ratio = our_price / competitor_price
        
        if price_ratio > 1.1:  # We're 10%+ more expensive
            return 0.95  # Reduce our price by 5%
        elif price_ratio < 0.9:  # We're more than 10% cheaper
            return 1.05  # Increase our price by 5%
        
        return 1.0  # Keep as is
    
    # ========================================================================
    # 2. DYNAMIC QUOTA ALLOCATION
    # ========================================================================
    
    def optimize_quota_allocation(
        self,
        train_id: int,
        travel_date: str,
        total_seats: int,
        quota_demands: Dict[QuotaType, float],  # Predicted demand (0-1) for each quota
        expected_cancellations: Dict[QuotaType, float],  # Expected cancellation rate
    ) -> QuotaAllocation:
        """
        Dynamically allocate seats between quotas to maximize revenue.
        
        Uses predicted demand and cancellation rates to adjust traditional IRCTC quotas.
        """
        allocation = QuotaAllocation(
            train_id=train_id,
            travel_date=travel_date,
            total_seats=total_seats
        )
        
        # Start with default allocations
        allocations = allocation._default_allocations()
        
        # Adjust based on demand forecasts
        total_demand = sum(quota_demands.values())
        if total_demand > 0:
            adjusted = {}
            for quota_type, base_seats in allocations.items():
                demand_weight = quota_demands.get(quota_type, 0.5) / total_demand
                adjusted[quota_type] = max(
                    int(total_seats * 0.05),  # Minimum 5% per quota
                    int(total_seats * demand_weight)
                )
            
            # Normalize to total seats
            total_allocated = sum(adjusted.values())
            if total_allocated > total_seats:
                # Scale down proportionally
                factor = total_seats / total_allocated
                allocations = {
                    q: max(int(s * factor), 1)
                    for q, s in adjusted.items()
                }
        
        allocation.allocations = allocations
        
        # Calculate revenue projection
        # (Simplified: assumes higher demand quota = higher price)
        quota_prices = {
            QuotaType.TATKAL: 1.5,  # Tatkal typically 50% premium
            QuotaType.LADIES: 1.0,
            QuotaType.SENIOR_CITIZEN: 0.8,  # Senior discount
            QuotaType.DEFENCE: 1.0,
            QuotaType.GENERAL: 1.0,
            QuotaType.FOREIGN_TOURIST: 1.2,
        }
        
        projected_revenue = sum(
            seats * quota_prices.get(quota_type, 1.0)
            for quota_type, seats in allocations.items()
        )
        allocation.revenue_projection = projected_revenue
        
        logger.info(
            f"Quota allocation for train {train_id} on {travel_date}: "
            f"{allocations}, projected revenue: {projected_revenue}"
        )
        
        return allocation
    
    # ========================================================================
    # 3. OVERBOOKING OPTIMIZATION
    # ========================================================================
    
    def calculate_overbooking_strategy(
        self,
        train_id: int,
        quota_type: QuotaType,
        seats_allocated: int,
        predicted_cancellation_rate: float,
        max_overbooking_pct: float = 0.15,  # Max 15% overbooking
    ) -> OverbookingStrategy:
        """
        Calculate optimal overbooking for a quota.
        
        Overbooking minimizes empty seats while managing compensation risk.
        """
        strategy = OverbookingStrategy(
            train_id=train_id,
            quota_type=quota_type,
            predicted_cancellation_rate=predicted_cancellation_rate,
            overbooking_percentage=max_overbooking_pct,
            seats_allocated=seats_allocated,
        )
        
        logger.info(
            f"Overbooking strategy for train {train_id}, {quota_type.value}: "
            f"{strategy.seats_overbooked} additional seats (cancellation rate: {predicted_cancellation_rate})"
        )
        
        return strategy
    
    # ========================================================================
    # 4. PRICE ELASTICITY & DEMAND MODELING
    # ========================================================================
    
    def estimate_demand_at_price(
        self,
        base_demand: float,
        current_price: float,
        proposed_price: float,
        elasticity: float = -0.8,
    ) -> float:
        """
        Estimate demand at a different price using elasticity.
        
        Formula: New Demand = Base Demand * (New Price / Current Price) ^ Elasticity
        """
        if current_price == 0:
            return base_demand
        
        price_ratio = proposed_price / current_price
        demand_multiplier = price_ratio ** elasticity
        new_demand = base_demand * demand_multiplier
        
        return max(0, new_demand)
    
    def find_revenue_optimal_price(
        self,
        base_price: float,
        base_demand: float,
        elasticity: float = -0.8,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Find price that maximizes revenue = price * demand.
        
        Returns: (optimal_price, max_revenue)
        """
        if min_price is None:
            min_price = base_price * self.BASE_PRICE_MULTIPLIER_RANGE[0]
        if max_price is None:
            max_price = base_price * self.BASE_PRICE_MULTIPLIER_RANGE[1]
        
        # Try different prices and find maximum revenue
        best_price = base_price
        best_revenue = base_price * base_demand
        
        for price in np.linspace(min_price, max_price, 50):
            demand = self.estimate_demand_at_price(
                base_demand, base_price, price, elasticity
            )
            revenue = price * demand
            
            if revenue > best_revenue:
                best_revenue = revenue
                best_price = price
        
        return round(best_price, 2), round(best_revenue, 2)
    
    # ========================================================================
    # 5. REVENUE ANALYTICS
    # ========================================================================
    
    def get_segment_revenue_stats(self) -> Dict:
        """Get revenue statistics across all segments."""
        if not self.segment_revenues:
            return {}
        
        revenues = [s.revenue for s in self.segment_revenues.values()]
        
        return {
            'total_segments': len(self.segment_revenues),
            'total_revenue': sum(revenues),
            'average_revenue_per_segment': np.mean(revenues),
            'max_revenue_segment': max(revenues),
            'min_revenue_segment': min(revenues),
            'std_dev': np.std(revenues),
        }
    
    def forecast_daily_revenue(
        self,
        trains: List[Dict],
        average_occupancy: float = 0.7,
    ) -> float:
        """
        Forecast daily revenue across all trains.
        
        Simplified: sum of (base_fare * expected_passengers * multiplier)
        """
        total_revenue = 0.0
        
        for train in trains:
            base_fare = train.get('base_fare', 500)
            total_seats = train.get('total_seats', 100)
            expected_passengers = int(total_seats * average_occupancy)
            
            # Simple multiplier based on demand
            multiplier = 1.0  # Would be calculated from ML models
            
            train_revenue = base_fare * expected_passengers * multiplier
            total_revenue += train_revenue
        
        return round(total_revenue, 2)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

yield_management_engine = YieldManagementEngine()
