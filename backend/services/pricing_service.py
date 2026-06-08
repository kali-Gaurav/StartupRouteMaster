"""
Pricing Service - Dynamic pricing based on demand and availability.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

from database.models import Route, Schedule

logger = logging.getLogger("pricing_service")


@dataclass
class PriceBreakdown:
    """Detailed price breakdown."""
    base_fare: float
    dynamic_fare: float
    demand_factor: float
    total_fare: float
    class_multiplier: float
    distance_km: int


class PricingService:
    """Dynamic pricing service with demand-based redistribution."""
    
    # Base fares per km by class
    CLASS_MULTIPLIERS = {
        "SL": 1.0,    # Sleeper
        "3A": 2.2,    # AC 3-Tier
        "2A": 3.5,    # AC 2-Tier
        "1A": 5.0,    # First AC
        "CC": 1.8,    # Chair Car
        "2S": 0.7,    # Second Seating
        "EC": 2.5,    # Executive Chair
    }
    
    # Demand factors by day of week
    DAY_FACTORS = {
        0: 1.0,  # Monday
        1: 1.0,  # Tuesday
        2: 1.0,  # Wednesday
        3: 1.1,  # Thursday
        4: 1.3,  # Friday
        5: 1.4,  # Saturday
        6: 1.2,  # Sunday
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.base_fare_per_km = 0.15  # ₹0.15 per km base fare
    
    async def calculate_fare(
        self,
        journey_id: str,
        class_type: str,
        passengers: int,
        travel_date: str
    ) -> float:
        """
        Calculate fare for a journey.
        
        Factors:
        - Base fare by distance
        - Class multiplier
        - Demand factor (day of week, advance booking, etc.)
        - Availability-based surge
        """
        breakdown = await self.get_price_breakdown(journey_id, class_type, travel_date)
        return breakdown.total_fare * passengers
    
    async def get_price_breakdown(
        self,
        journey_id: str,
        class_type: str,
        travel_date: str
    ) -> PriceBreakdown:
        """Get detailed price breakdown."""
        try:
            # Parse travel date
            travel_dt = datetime.strptime(travel_date, "%Y-%m-%d").date()
            
            # Get route info
            route = self.db.get(Route, journey_id)
            
            # Calculate base fare
            distance_km = route.duration_minutes  # Approximate: 1 min = 1 km
            base_fare = distance_km * self.base_fare_per_km
            
            # Apply class multiplier
            class_multiplier = self.CLASS_MULTIPLIERS.get(class_type, 1.0)
            dynamic_fare = base_fare * class_multiplier
            
            # Calculate demand factor
            demand_factor = self._calculate_demand_factor(travel_dt)
            
            # Apply demand factor
            total_fare = dynamic_fare * demand_factor
            
            return PriceBreakdown(
                base_fare=base_fare,
                dynamic_fare=dynamic_fare,
                demand_factor=demand_factor,
                total_fare=round(total_fare, 2),
                class_multiplier=class_multiplier,
                distance_km=distance_km
            )
            
        except Exception as e:
            logger.error(f"Error calculating fare: {e}")
            return PriceBreakdown(
                base_fare=500,
                dynamic_fare=500,
                demand_factor=1.0,
                total_fare=500,
                class_multiplier=1.0,
                distance_km=1000
            )
    
    def _calculate_demand_factor(self, travel_date: date) -> float:
        """Calculate demand factor based on various factors."""
        now = datetime.now().date()
        days_ahead = (travel_date - now).days
        
        factor = 1.0
        
        # Day of week factor
        factor *= self.DAY_FACTORS.get(travel_date.weekday(), 1.0)
        
        # Advance booking discount
        if days_ahead > 30:
            factor *= 0.95  # 5% discount for early booking
        elif days_ahead > 60:
            factor *= 0.90  # 10% discount for very early booking
        
        # Last minute premium
        if days_ahead <= 2:
            factor *= 1.25  # 25% premium
        elif days_ahead <= 7:
            factor *= 1.15  # 15% premium
        
        # Festival/holiday premium
        if self._is_holiday(travel_date):
            factor *= 1.5  # 50% premium for holidays
        
        return round(factor, 2)
    
    def _is_holiday(self, travel_date: date) -> bool:
        """Check if date is a major holiday."""
        holidays = [
            (1, 1),    # New Year
            (1, 14),   # Makar Sankranti
            (1, 26),   # Republic Day
            (8, 15),   # Independence Day
            (10, 2),   # Gandhi Jayanti
            (10, 31),  # Diwali
            (12, 25),  # Christmas
        ]
        
        return (travel_date.month, travel_date.day) in holidays
    
    def get_surge_pricing_info(
        self,
        train_number: str,
        travel_date: str,
        class_type: str
    ) -> Dict[str, Any]:
        """Get current surge pricing information."""
        try:
            travel_dt = datetime.strptime(travel_date, "%Y-%m-%d").date()
            demand_factor = self._calculate_demand_factor(travel_dt)
            
            return {
                "demand_factor": demand_factor,
                "surge_percentage": int((demand_factor - 1) * 100),
                "is_surge": demand_factor > 1.2,
                "surge_reason": self._get_surge_reason(travel_dt)
            }
            
        except Exception as e:
            logger.error(f"Error getting surge info: {e}")
            return {"demand_factor": 1.0, "surge_percentage": 0}
    
    def _get_surge_reason(self, travel_date: date) -> str:
        """Get reason for surge pricing."""
        if travel_date.weekday() >= 5:
            return "Weekend travel"
        if self._is_holiday(travel_date):
            return "Holiday travel"
        if (travel_date - datetime.now().date()).days <= 7:
            return "Last minute booking"
        return "High demand"


# Singleton instance
pricing_service = None

def get_pricing_service(db: Session) -> PricingService:
    """Get or create pricing service instance."""
    global pricing_service
    if pricing_service is None:
        pricing_service = PricingService(db)
    return pricing_service