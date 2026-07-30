"""
Delay-Aware Routing Service
Integrates delay predictions into route search and scoring
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass

logger = logging.getLogger("routing.delay_aware")

@dataclass
class DelayInfo:
    """Delay information for a train/leg"""
    train_number: str
    predicted_delay_minutes: float
    confidence: float
    historical_on_time_percentage: float
    delay_category: str  # "on_time", "minor_delay", "major_delay", "cancelled"


class DelayAwareRoutingService:
    """
    Integrates delay predictions into route search and scoring.
    Adjusts arrival times and route scores based on predicted delays.
    """
    
    # Delay thresholds (in minutes)
    ON_TIME_THRESHOLD = 5
    MINOR_DELAY_THRESHOLD = 30
    MAJOR_DELAY_THRESHOLD = 120
    
    # Score penalties per minute of delay
    DELAY_PENALTY_PER_MINUTE = 0.01
    MAJOR_DELAY_PENALTY = 50.0
    
    def __init__(self):
        self._delay_predictor = None
        self._delay_cache: Dict[str, DelayInfo] = {}
        self._cache_ttl = timedelta(minutes=15)
    
    def _get_delay_predictor(self):
        """Lazy load delay predictor to avoid circular imports"""
        if self._delay_predictor is None:
            try:
                from services.delay_predictor import DelayPredictor
                self._delay_predictor = DelayPredictor()
            except ImportError:
                logger.warning("Delay predictor not available, using fallback")
                self._delay_predictor = None
        return self._delay_predictor
    
    def _get_cache_key(self, train_number: str, travel_date: date) -> str:
        """Generate cache key for delay prediction"""
        return f"{train_number}:{travel_date.isoformat()}"
    
    async def predict_leg_delay(
        self, 
        train_number: str, 
        travel_date: date,
        departure_hour: int = 12
    ) -> DelayInfo:
        """
        Predict delay for a train leg.
        
        Args:
            train_number: Train number
            travel_date: Travel date
            departure_hour: Hour of departure (for pattern matching)
            
        Returns:
            DelayInfo with prediction details
        """
        cache_key = self._get_cache_key(train_number, travel_date)
        
        # Check cache
        if cache_key in self._delay_cache:
            cached = self._delay_cache[cache_key]
            # Check if cache is still valid
            # For simplicity, always return cached for now
            return cached
        
        try:
            # Try using ML predictor
            predictor = self._get_delay_predictor()
            
            if predictor and hasattr(predictor, 'predict_delay'):
                predicted_delay = await predictor.predict_delay(
                    train_id=hash(train_number) % 100000,
                    day_of_week=travel_date.weekday(),
                    month=travel_date.month,
                    departure_hour=departure_hour,
                    past_delay_avg=0,
                    weather_score=0.5
                )
            else:
                # Fallback to rule-based prediction
                predicted_delay = self._predict_rule_based(train_number, travel_date, departure_hour)
            
            # Determine delay category
            delay_category = self._categorize_delay(predicted_delay)
            
            # Get historical on-time percentage (simplified)
            on_time_pct = self._get_historical_on_time(train_number)
            
            # Calculate confidence (lower for longer predictions)
            confidence = self._calculate_confidence(travel_date)
            
            delay_info = DelayInfo(
                train_number=train_number,
                predicted_delay_minutes=predicted_delay,
                confidence=confidence,
                historical_on_time_percentage=on_time_pct,
                delay_category=delay_category
            )
            
            # Cache result
            self._delay_cache[cache_key] = delay_info
            
            return delay_info
            
        except Exception as e:
            logger.error(f"Delay prediction failed for {train_number}: {e}")
            # Return default (on-time) prediction
            return DelayInfo(
                train_number=train_number,
                predicted_delay_minutes=0.0,
                confidence=0.0,
                historical_on_time_percentage=90.0,
                delay_category="on_time"
            )
    
    def _predict_rule_based(
        self, 
        train_number: str, 
        travel_date: date,
        departure_hour: int
    ) -> float:
        """
        Rule-based delay prediction as fallback.
        Uses historical patterns and time-based rules.
        """
        delay = 0.0
        
        # Rush hour factor (7-9 AM, 5-8 PM)
        if departure_hour in [7, 8, 9, 17, 18, 19, 20]:
            delay += 5.0
        
        # Weekend factor
        if travel_date.weekday() in [5, 6]:
            delay += 10.0  # More crowded on weekends
        
        # Monsoon factor (June-September)
        if travel_date.month in [6, 7, 8, 9]:
            delay += 15.0
        
        # Festival season
        if travel_date.month in [10, 11, 12]:
            delay += 20.0
        
        # Winter fog (December-January)
        if travel_date.month in [12, 1]:
            delay += 25.0
        
        # Add some randomness
        import random
        delay += random.uniform(0, 10)
        
        return delay
    
    def _categorize_delay(self, delay_minutes: float) -> str:
        """Categorize delay severity"""
        if delay_minutes <= self.ON_TIME_THRESHOLD:
            return "on_time"
        elif delay_minutes <= self.MINOR_DELAY_THRESHOLD:
            return "minor_delay"
        elif delay_minutes <= self.MAJOR_DELAY_THRESHOLD:
            return "major_delay"
        else:
            return "cancelled"  # Very long delay treated as potential cancellation
    
    def _get_historical_on_time(self, train_number: str) -> float:
        """Get historical on-time percentage for a train"""
        # Simplified - could query database for actual data
        # Most Indian trains have ~80-90% on-time performance
        return 85.0
    
    def _calculate_confidence(self, travel_date: date) -> float:
        """Calculate prediction confidence based on how far in advance"""
        days_ahead = (travel_date - date.today()).days
        
        if days_ahead <= 1:
            return 0.95  # Very high confidence for today/tomorrow
        elif days_ahead <= 3:
            return 0.85
        elif days_ahead <= 7:
            return 0.75
        elif days_ahead <= 14:
            return 0.65
        else:
            return 0.50  # Lower confidence for advance predictions
    
    async def apply_delay_to_routes(
        self, 
        routes: List[Any], 
        travel_date: date
    ) -> List[Any]:
        """
        Apply delay predictions to routes and adjust scores.
        
        Args:
            routes: List of route objects
            travel_date: Travel date
            
        Returns:
            Routes with delay information applied
        """
        for route in routes:
            total_delay = 0.0
            has_major_delay = False
            
            # Process each leg in the route
            if hasattr(route, 'legs') and route.legs:
                for leg in route.legs:
                    if hasattr(leg, 'train_number'):
                        # Get delay prediction
                        delay_info = await self.predict_leg_delay(
                            leg.train_number,
                            travel_date,
                            departure_hour=getattr(leg, 'departure_hour', 12)
                        )
                        
                        # Apply delay to leg
                        if hasattr(leg, 'delay_minutes'):
                            leg.delay_minutes = delay_info.predicted_delay_minutes
                        
                        if hasattr(leg, 'arrival'):
                            # Adjust arrival time
                            delay = timedelta(minutes=delay_info.predicted_delay_minutes)
                            leg.arrival = leg.arrival + delay
                        
                        if hasattr(leg, 'delayed_arrival'):
                            leg.delayed_arrival = leg.arrival + delay
                        
                        # Track total delay
                        total_delay += delay_info.predicted_delay_minutes
                        
                        # Check for major delays
                        if delay_info.delay_category in ["major_delay", "cancelled"]:
                            has_major_delay = True
            
            # Apply delay penalty to route score
            if hasattr(route, 'score'):
                # Penalize score based on total delay
                delay_penalty = total_delay * self.DELAY_PENALTY_PER_MINUTE
                
                # Extra penalty for major delays
                if has_major_delay:
                    delay_penalty += self.MAJOR_DELAY_PENALTY
                
                route.score = max(0, route.score - delay_penalty)
            
            # Store delay info on route
            if hasattr(route, 'total_delay_minutes'):
                route.total_delay_minutes = total_delay
            
            if hasattr(route, 'has_major_delay'):
                route.has_major_delay = has_major_delay
        
        # Filter out routes with major delays if needed
        # (Could be made configurable)
        # routes = [r for r in routes if not getattr(r, 'has_major_delay', False)]
        
        return routes
    
    def calculate_delay_adjusted_duration(
        self,
        scheduled_duration_minutes: float,
        predicted_delay_minutes: float
    ) -> float:
        """Calculate actual travel time including predicted delay"""
        return scheduled_duration_minutes + predicted_delay_minutes
    
    def get_delay_warning_message(self, delay_info: DelayInfo) -> str:
        """Generate user-friendly delay warning message"""
        if delay_info.delay_category == "on_time":
            return ""
        elif delay_info.delay_category == "minor_delay":
            return f"Expected minor delay of ~{int(delay_info.predicted_delay_minutes)} minutes"
        elif delay_info.delay_category == "major_delay":
            return f"Expected delay of ~{int(delay_info.predicted_delay_minutes)} minutes. Consider alternative routes."
        else:
            return "Train may be cancelled. Check live status before traveling."


# Global instance
_delay_aware_routing: Optional[DelayAwareRoutingService] = None

def get_delay_aware_routing() -> DelayAwareRoutingService:
    """Get or create global delay-aware routing instance"""
    global _delay_aware_routing
    if _delay_aware_routing is None:
        _delay_aware_routing = DelayAwareRoutingService()
    return _delay_aware_routing
