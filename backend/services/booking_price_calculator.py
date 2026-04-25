"""
Booking Price Calculator - Integrates Pricing Service into Booking Flow
Handles dynamic pricing, surge calculation, and price breakdown for bookings
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass

logger = logging.getLogger("booking.price_calculator")

@dataclass
class PriceBreakdown:
    """Detailed price breakdown for a booking"""
    base_fare: float
    dynamic_surge: float
    surge_multiplier: float
    platform_fee: float
    total: float
    currency: str = "INR"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_fare": round(self.base_fare, 2),
            "dynamic_surge": round(self.dynamic_surge, 2),
            "surge_multiplier": round(self.surge_multiplier, 2),
            "platform_fee": round(self.platform_fee, 2),
            "total": round(self.total, 2),
            "currency": self.currency
        }


class BookingPriceCalculator:
    """
    Calculates booking prices by integrating the Pricing Service
    with booking flow. Handles dynamic surge, yield management, and discounts.
    """
    
    PLATFORM_FEE_PERCENTAGE = 0.02  # 2% platform fee
    MIN_PLATFORM_FEE = 10.0  # Minimum ₹10
    MAX_PLATFORM_FEE = 100.0  # Maximum ₹100
    
    def __init__(self, db=None):
        self.db = db
        self._pricing_service = None
    
    def _get_pricing_service(self):
        """Lazy load pricing service to avoid circular imports"""
        if self._pricing_service is None:
            from services.pricing_service import PricingService
            self._pricing_service = PricingService()
        return self._pricing_service
    
    async def calculate_booking_price(
        self,
        source: str,
        destination: str,
        travel_date: date,
        passenger_count: int,
        train_class: str = "SL",
        user_id: Optional[str] = None,
        route_id: Optional[str] = None
    ) -> PriceBreakdown:
        """
        Calculate complete price for a booking including dynamic surge.
        
        Args:
            source: Source station code
            destination: Destination station code  
            travel_date: Travel date
            passenger_count: Number of passengers
            train_class: Train class (SL, 3A, 2A, 1A, etc.)
            user_id: User ID for intent tracking
            route_id: Route ID for historical data
            
        Returns:
            PriceBreakdown with all price components
        """
        try:
            # Get base fare from route data
            base_fare = await self._get_base_fare(source, destination, train_class, route_id)
            
            # Get dynamic surge from pricing service
            surge_multiplier = await self._calculate_surge(
                source, destination, travel_date, passenger_count
            )
            
            # Calculate surge amount
            dynamic_surge = (base_fare * surge_multiplier) - base_fare
            
            # Calculate platform fee
            subtotal = base_fare + dynamic_surge
            platform_fee = self._calculate_platform_fee(subtotal)
            
            # Calculate total per passenger
            passenger_total = base_fare + dynamic_surge + platform_fee
            
            # Calculate total for all passengers
            total = passenger_total * passenger_count
            
            return PriceBreakdown(
                base_fare=base_fare,
                dynamic_surge=dynamic_surge,
                surge_multiplier=surge_multiplier,
                platform_fee=platform_fee,
                total=total
            )
            
        except Exception as e:
            logger.error(f"Price calculation failed: {e}")
            # Return fallback price
            return self._get_fallback_price(passenger_count, train_class)
    
    async def _get_base_fare(self, source: str, destination: str, train_class: str, route_id: Optional[str] = None) -> float:
        """Get base fare from route data or use class-based defaults."""
        # Prefer explicit route/trip fare if available
        if self.db and route_id:
            try:
                from database.models import Fare, Trip
                trip_query = self.db.query(Trip)
                try:
                    trip_query = trip_query.filter(Trip.id == int(route_id))
                except ValueError:
                    trip_query = trip_query.filter(Trip.trip_id == route_id)
                trip = trip_query.first()
                if trip:
                    fare = self.db.query(Fare).filter(
                        Fare.trip_id == trip.id,
                        Fare.class_type.ilike(train_class)
                    ).order_by(Fare.amount).first()
                    if fare:
                        return float(fare.amount)
            except Exception as e:
                logger.debug(f"Base fare DB lookup failed: {e}")

        if self.db and source and destination:
            try:
                from database.models import Fare, Trip, StopTime, Stop
                # Find candidate trips for source/destination pair
                trip_ids = (
                    self.db.query(Trip.id)
                    .join(StopTime, StopTime.trip_id == Trip.id)
                    .join(Stop, Stop.id == StopTime.stop_id)
                    .filter(Stop.code == source)
                    .subquery()
                )
                fare = self.db.query(Fare).filter(
                    Fare.trip_id.in_(trip_ids),
                    Fare.class_type.ilike(train_class)
                ).order_by(Fare.amount).first()
                if fare:
                    return float(fare.amount)
            except Exception as e:
                logger.debug(f"Base fare broad DB lookup failed: {e}")

        return self._get_class_default(train_class)
    
    def _get_class_default(self, train_class: str) -> float:
        """Get default fare by train class"""
        class_fares = {
            "1A": 1200,  # First AC
            "2A": 800,   # Second AC  
            "3A": 500,   # Third AC
            "SL": 200,   # Sleeper
            "CC": 300,   # Chair Car
            "EC": 600,   # Executive Chair
        }
        return class_fares.get(train_class, 300)
    
    async def _calculate_surge(
        self, 
        source: str, 
        destination: str, 
        travel_date: date,
        passenger_count: int
    ) -> float:
        """
        Calculate dynamic surge multiplier based on demand.
        Uses pricing service when available, falls back to rule-based surge.
        """
        try:
            # Try using pricing service
            pricing_service = self._get_pricing_service()
            
            if hasattr(pricing_service, 'get_dynamic_unlock_fee'):
                # Use the pricing service's dynamic fee calculation
                fee = await pricing_service.get_dynamic_unlock_fee(
                    self.db,
                    source,
                    destination,
                    seats_available=None,
                    user_id=None
                )
                
                # Convert fee to surge multiplier
                base_fee = self._get_class_default("SL")
                if base_fee > 0:
                    return fee / base_fee
            
            # Fallback to rule-based surge
            return self._calculate_rule_based_surge(travel_date, passenger_count)
            
        except Exception as e:
            logger.warning(f"Dynamic surge calculation failed, using rules: {e}")
            return self._calculate_rule_based_surge(travel_date, passenger_count)
    
    def _calculate_rule_based_surge(self, travel_date: date, passenger_count: int) -> float:
        """
        Rule-based surge calculation as fallback.
        Considers day of week, proximity to travel date, and demand factors.
        """
        surge = 1.0
        
        # Day of week factor
        day_of_week = travel_date.weekday()
        if day_of_week in [4, 5, 6]:  # Fri, Sat, Sun
            surge += 0.15  # 15% surge for weekend
        
        # Days until departure factor
        days_ahead = (travel_date - date.today()).days
        if days_ahead < 3:
            surge += 0.30  # 30% surge for last-minute
        elif days_ahead < 7:
            surge += 0.15  # 15% surge for this week
        elif days_ahead > 30:
            surge -= 0.10  # 10% discount for advance booking
        
        # Group size factor (larger groups = higher demand)
        if passenger_count >= 4:
            surge += 0.10
        
        # Festival/holiday factor (simplified - could be expanded)
        # Check for common holiday periods
        month = travel_date.month
        if month in [10, 11, 12]:  # Festival season
            surge += 0.20
        elif month in [4, 5]:  # Summer vacation
            surge += 0.15
        
        # Cap surge between 0.8x and 2.0x
        return max(0.8, min(2.0, surge))
    
    def _calculate_platform_fee(self, subtotal: float) -> float:
        """Calculate platform fee with min/max caps"""
        fee = subtotal * self.PLATFORM_FEE_PERCENTAGE
        return max(self.MIN_PLATFORM_FEE, min(self.MAX_PLATFORM_FEE, fee))
    
    def _get_fallback_price(self, passenger_count: int, train_class: str) -> PriceBreakdown:
        """Get fallback price when calculation fails"""
        base_fare = self._get_class_default(train_class)
        platform_fee = self._calculate_platform_fee(base_fare)
        total = (base_fare + platform_fee) * passenger_count
        
        return PriceBreakdown(
            base_fare=base_fare,
            dynamic_surge=0.0,
            surge_multiplier=1.0,
            platform_fee=platform_fee,
            total=total
        )
    
    async def calculate_refund_amount(
        self,
        original_total: float,
        cancellation_time: datetime,
        travel_date: date,
        passenger_count: int
    ) -> float:
        """
        Calculate refund amount based on cancellation policy.
        Returns the refundable amount after deducting cancellation charges.
        """
        # Days until travel
        days_until = (travel_date - cancellation_time.date()).days
        
        # Cancellation charge tiers
        if days_until >= 10:
            cancellation_charge = 0.10  # 10% charge
        elif days_until >= 5:
            cancellation_charge = 0.25  # 25% charge
        elif days_until >= 2:
            cancellation_charge = 0.50  # 50% charge
        elif days_until >= 1:
            cancellation_charge = 0.75  # 75% charge
        else:
            cancellation_charge = 1.00  # 100% charge (no refund)
        
        # Calculate refund
        refund = original_total * (1 - cancellation_charge)
        
        # Platform fee is non-refundable
        platform_fee = self.MIN_PLATFORM_FEE * passenger_count
        refund = max(0, refund - platform_fee)
        
        return round(refund, 2)


# Global instance for easy access
_booking_price_calculator: Optional[BookingPriceCalculator] = None

def get_booking_price_calculator(db=None) -> BookingPriceCalculator:
    """Get or create global price calculator instance"""
    global _booking_price_calculator
    if _booking_price_calculator is None:
        _booking_price_calculator = BookingPriceCalculator(db)
    return _booking_price_calculator