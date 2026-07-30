"""
Fare Service - Fare calculation and retrieval.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from database.models import Route, Schedule

logger = logging.getLogger("fare_service")


class FareService:
    """
    Service for fare calculation and retrieval.
    
    Features:
    - Base fare calculation
    - Dynamic pricing based on demand
    - Tatkal charges
    - Concession discounts
    """
    
    # Base fares per km by class
    CLASS_FARES = {
        "1A": 0.45,  # AC First Class
        "2A": 0.35,  # AC 2-Tier
        "3A": 0.25,  # AC 3-Tier
        "CC": 0.20,  # AC Chair Car
        "SL": 0.12,  # Sleeper
        "2S": 0.08,  # Second Sitting
    }
    
    # Tatkal charges
    TATKAL_CHARGES = {
        "1A": 500,
        "2A": 400,
        "3A": 300,
        "CC": 200,
        "SL": 200,
        "2S": 100
    }
    
    PREMIUM_TATKAL_MULTIPLIER = 1.5
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
    
    async def get_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str = "SL",
        quota_code: str = "GN",
        travel_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get fare for a journey.
        
        Args:
            train_no: Train number
            from_station: Origin station code
            to_station: Destination station code
            class_code: Class type (SL, 3A, 2A, etc.)
            quota_code: Quota (GN, TQ, SS, etc.)
            travel_date: Travel date (YYYY-MM-DD)
            
        Returns:
            Fare details dictionary
        """
        try:
            # Get route information
            route = self.db.query(Route).filter(
                Route.train_number == train_no,
                Route.source_code == from_station.upper(),
                Route.dest_code == to_station.upper()
            ).first()
            
            if not route:
                # Return fallback fare
                return self._get_fallback_fare(class_code, quota_code)
            
            # Calculate base fare
            base_fare = self._calculate_base_fare(route, class_code)
            
            # Get dynamic pricing factor
            demand_factor = await self._get_demand_factor(travel_date)
            
            # Calculate total fare
            total_fare = base_fare * demand_factor
            
            # Add Tatkal charges if applicable
            tatkal = 0
            if quota_code in ["TQ", "PT"]:
                tatkal = self.TATKAL_CHARGES.get(class_code, 200)
                if quota_code == "PT":
                    tatkal = int(tatkal * self.PREMIUM_TATKAL_MULTIPLIER)
                total_fare += tatkal
            
            return {
                "success": True,
                "data": {
                    "train_no": train_no,
                    "from_station": from_station,
                    "to_station": to_station,
                    "class_code": class_code,
                    "quota_code": quota_code,
                    "base_fare": round(base_fare, 2),
                    "demand_factor": demand_factor,
                    "tatkal_charge": tatkal,
                    "total_fare": round(total_fare, 2),
                    "currency": "INR"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting fare: {e}")
            return self._get_fallback_fare(class_code, quota_code)
    
    async def get_fare_with_fallback(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str = "SL",
        quota_code: str = "GN"
    ) -> Dict[str, Any]:
        """Get fare with fallback to default values."""
        result = await self.get_fare(
            train_no=train_no,
            from_station=from_station,
            to_station=to_station,
            class_code=class_code,
            quota_code=quota_code
        )
        
        if not result.get("success"):
            return self._get_fallback_fare(class_code, quota_code)
        
        return result
    
    def _calculate_base_fare(
        self,
        route: Route,
        class_code: str
    ) -> float:
        """Calculate base fare based on distance and class."""
        # Use duration as proxy for distance (1 minute ≈ 1 km)
        distance_km = route.duration_minutes
        
        # Get fare per km for class
        fare_per_km = self.CLASS_FARES.get(class_code, 0.12)
        
        # Calculate base fare
        base_fare = distance_km * fare_per_km
        
        # Minimum fare
        min_fares = {
            "1A": 500,
            "2A": 400,
            "3A": 300,
            "CC": 200,
            "SL": 100,
            "2S": 50
        }
        
        return max(base_fare, min_fares.get(class_code, 100))
    
    async def _get_demand_factor(
        self,
        travel_date: Optional[str]
    ) -> float:
        """Calculate demand factor based on date."""
        if not travel_date:
            return 1.0
        
        try:
            date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            days_ahead = (date_obj - today).days
            
            factor = 1.0
            
            # Weekend premium
            if date_obj.weekday() >= 5:  # Saturday or Sunday
                factor *= 1.15
            
            # Festival/holiday premium
            if self._is_holiday(date_obj):
                factor *= 1.5
            
            # Last minute premium
            if days_ahead <= 3:
                factor *= 1.25
            elif days_ahead <= 7:
                factor *= 1.15
            
            # Advance booking discount
            if days_ahead > 30:
                factor *= 0.95
            
            return round(factor, 2)
            
        except Exception:
            return 1.0
    
    def _is_holiday(self, date_obj) -> bool:
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
        
        return (date_obj.month, date_obj.day) in holidays
    
    def _get_fallback_fare(
        self,
        class_code: str,
        quota_code: str = "GN"
    ) -> Dict[str, Any]:
        """Get fallback fare when data is unavailable."""
        base_fares = {
            "1A": 3500,
            "2A": 2500,
            "3A": 1500,
            "CC": 1000,
            "SL": 500,
            "2S": 300
        }
        
        base_fare = base_fares.get(class_code, 500)
        
        # Add Tatkal if applicable
        tatkal = 0
        if quota_code in ["TQ", "PT"]:
            tatkal = self.TATKAL_CHARGES.get(class_code, 200)
            if quota_code == "PT":
                tatkal = int(tatkal * self.PREMIUM_TATKAL_MULTIPLIER)
        
        return {
            "success": True,
            "data": {
                "class_code": class_code,
                "quota_code": quota_code,
                "base_fare": base_fare,
                "demand_factor": 1.0,
                "tatkal_charge": tatkal,
                "total_fare": base_fare + tatkal,
                "currency": "INR",
                "fallback": True
            }
        }
    
    async def calculate_concession(
        self,
        class_code: str,
        passenger_age: int,
        passenger_gender: str,
        concession_type: Optional[str] = None
    ) -> float:
        """Calculate concession discount for eligible passengers."""
        # Default: no concession
        discount = 0.0
        
        if not concession_type:
            return discount
        
        # Senior Citizen (60+)
        if concession_type == "senior_citizen":
            if passenger_age >= 60:
                discount = 0.40  # 40% discount
                if passenger_gender == "F":
                    discount = 0.50  # 50% for women senior citizens
        
        # Ladies/Women
        elif concession_type == "ladies":
            if passenger_gender == "F":
                discount = 0.25  # 25% discount
        
        # Divyang (Persons with Disabilities)
        elif concession_type == "divyang":
            discount = 0.50  # 50% discount
        
        # Military Personnel
        elif concession_type == "military":
            discount = 0.30  # 30% discount
        
        return discount


# Singleton instance
fare_service = None

def get_fare_service(db: Session) -> FareService:
    """Get or create fare service instance."""
    global fare_service
    if fare_service is None:
        fare_service = FareService(db)
    return fare_service