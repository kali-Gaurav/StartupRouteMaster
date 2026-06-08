"""
Real-Time Route Hydration Service
Integrates live status data into route search results
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger("routing.realtime_hydration")

@dataclass
class LiveTrainStatus:
    """Live status information for a train"""
    train_number: str
    train_name: str
    current_station: str
    delay_minutes: int
    is_cancelled: bool
    last_updated: datetime
    next_station: Optional[str] = None
    eta_next_station: Optional[datetime] = None


class RealtimeRouteHydrationService:
    """
    Hydrates route search results with real-time data.
    Injects live delays, cancellations, and availability into routes.
    """
    
    # Cache TTL for live status
    CACHE_TTL_MINUTES = 5
    BATCH_SIZE = 50  # Process trains in batches
    
    def __init__(self):
        self._live_status_service = None
        self._status_cache: Dict[str, LiveTrainStatus] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def _get_live_status_service(self):
        """Lazy load live status service"""
        if self._live_status_service is None:
            try:
                from services.live_status_service import LiveStatusService
                self._live_status_service = LiveStatusService()
            except ImportError:
                logger.warning("Live status service not available")
                self._live_status_service = None
        return self._live_status_service
    
    def _get_cache_key(self, train_number: str, travel_date: date) -> str:
        """Generate cache key for status"""
        return f"{train_number}:{travel_date.isoformat()}"
    
    def _is_cache_valid(self, train_number: str, travel_date: date) -> bool:
        """Check if cached status is still valid"""
        key = self._get_cache_key(train_number, travel_date)
        if key not in self._cache_timestamps:
            return False
        
        age = datetime.utcnow() - self._cache_timestamps[key]
        return age < timedelta(minutes=self.CACHE_TTL_MINUTES)
    
    async def get_train_status(
        self,
        train_number: str,
        travel_date: date
    ) -> Optional[LiveTrainStatus]:
        """
        Get live status for a train.
        Uses cache to avoid excessive API calls.
        """
        cache_key = self._get_cache_key(train_number, travel_date)
        
        # Return cached if valid
        if cache_key in self._status_cache and self._is_cache_valid(train_number, travel_date):
            return self._status_cache[cache_key]
        
        try:
            # Try live status service
            service = self._get_live_status_service()
            
            if service and hasattr(service, 'get_live_status'):
                status = await service.get_live_status(train_number)
            else:
                # Fallback to mock data
                status = self._get_mock_status(train_number)
            
            # Cache the result
            if status:
                self._status_cache[cache_key] = status
                self._cache_timestamps[cache_key] = datetime.utcnow()
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get live status for {train_number}: {e}")
            return None
    
    def _get_mock_status(self, train_number: str) -> LiveTrainStatus:
        """Generate mock status for testing"""
        return LiveTrainStatus(
            train_number=train_number,
            train_name=f"Train {train_number}",
            current_station="Unknown",
            delay_minutes=0,
            is_cancelled=False,
            last_updated=datetime.utcnow()
        )
    
    async def hydrate_routes(
        self,
        routes: List[Any],
        travel_date: date
    ) -> List[Any]:
        """
        Hydrate routes with real-time data.
        
        Args:
            routes: List of route objects from search
            travel_date: Travel date
            
        Returns:
            Routes with real-time data applied
        """
        if not routes:
            return routes
        
        # Collect all unique trains from all routes
        train_numbers = set()
        for route in routes:
            if hasattr(route, 'legs') and route.legs:
                for leg in route.legs:
                    if hasattr(leg, 'train_number') and leg.train_number:
                        train_numbers.add(leg.train_number)
        
        # Batch fetch statuses
        await self._prefetch_train_statuses(train_numbers, travel_date)
        
        # Apply status to routes
        for route in routes:
            await self._apply_status_to_route(route, travel_date)
        
        # Filter out cancelled trains
        routes = self._filter_cancelled_routes(routes)
        
        # Re-rank based on delay
        routes = self._rerank_by_delay(routes)
        
        return routes
    
    async def _prefetch_train_statuses(
        self,
        train_numbers: set,
        travel_date: date
    ):
        """Prefetch statuses for multiple trains"""
        # Process in batches to avoid overwhelming the API
        train_list = list(train_numbers)
        
        for i in range(0, len(train_list), self.BATCH_SIZE):
            batch = train_list[i:i + self.BATCH_SIZE]
            
            # Fetch in parallel
            tasks = [
                self.get_train_status(train_num, travel_date)
                for train_num in batch
            ]
            
            # Note: In production, use asyncio.gather with proper error handling
            # For now, sequential is safer
            for train_num in batch:
                await self.get_train_status(train_num, travel_date)
    
    async def _apply_status_to_route(self, route: Any, travel_date: date):
        """Apply live status to a single route"""
        if not hasattr(route, 'legs') or not route.legs:
            return
        
        total_delay = 0
        has_cancelled_leg = False
        
        for leg in route.legs:
            if not hasattr(leg, 'train_number') or not leg.train_number:
                continue
            
            # Get cached status
            status = await self.get_train_status(leg.train_number, travel_date)
            
            if status:
                # Apply delay
                if hasattr(leg, 'delay_minutes'):
                    leg.delay_minutes = status.delay_minutes
                
                # Adjust arrival time
                if hasattr(leg, 'arrival') and status.delay_minutes > 0:
                    delay = timedelta(minutes=status.delay_minutes)
                    if hasattr(leg, 'delayed_arrival'):
                        leg.delayed_arrival = leg.arrival + delay
                    else:
                        leg.arrival = leg.arrival + delay
                
                # Mark if cancelled
                if status.is_cancelled:
                    has_cancelled_leg = True
                    if hasattr(leg, 'is_cancelled'):
                        leg.is_cancelled = True
                
                # Track total delay
                total_delay += status.delay_minutes
        
        # Store aggregate info on route
        if hasattr(route, 'total_delay_minutes'):
            route.total_delay_minutes = total_delay
        
        if hasattr(route, 'has_cancelled_leg'):
            route.has_cancelled_leg = has_cancelled_leg
        
        # Mark route as non-viable if any leg is cancelled
        if has_cancelled_leg and hasattr(route, 'is_viable'):
            route.is_viable = False
    
    def _filter_cancelled_routes(self, routes: List[Any]) -> List[Any]:
        """Filter out routes with cancelled trains"""
        # Option 1: Remove completely
        # return [r for r in routes if not getattr(r, 'has_cancelled_leg', False)]
        
        # Option 2: Mark but keep (with warning)
        for route in routes:
            if getattr(route, 'has_cancelled_leg', False):
                if hasattr(route, 'warning_message'):
                    route.warning_message = "Contains cancelled train(s)"
                else:
                    route.warning = "CANCELLED_TRAIN"
        
        return routes
    
    def _rerank_by_delay(self, routes: List[Any]) -> List[Any]:
        """Re-rank routes based on delay information"""
        # Sort by total delay (less delay = better)
        valid_routes = [r for r in routes if not getattr(r, 'has_cancelled_leg', False)]
        
        # Add delay penalty to score
        for route in valid_routes:
            delay = getattr(route, 'total_delay_minutes', 0)
            if hasattr(route, 'score') and delay > 0:
                # Reduce score by 0.5 points per minute of delay
                route.score = max(0, route.score - (delay * 0.5))
        
        # Re-sort
        valid_routes.sort(key=lambda r: (
            getattr(r, 'has_cancelled_leg', False),  # False (0) < True (1)
            getattr(r, 'total_delay_minutes', 0)     # Less delay first
        ))
        
        return valid_routes
    
    async def get_delay_impact_summary(
        self,
        routes: List[Any]
    ) -> Dict[str, Any]:
        """Get summary of delay impact across all routes"""
        total_routes = len(routes)
        routes_with_delays = 0
        total_delay_minutes = 0
        cancelled_routes = 0
        
        for route in routes:
            delay = getattr(route, 'total_delay_minutes', 0)
            if delay > 0:
                routes_with_delays += 1
                total_delay_minutes += delay
            
            if getattr(route, 'has_cancelled_leg', False):
                cancelled_routes += 1
        
        return {
            "total_routes": total_routes,
            "routes_with_delays": routes_with_delays,
            "percentage_with_delays": round(routes_with_delays / total_routes * 100, 1) if total_routes > 0 else 0,
            "cancelled_routes": cancelled_routes,
            "average_delay_minutes": round(total_delay_minutes / routes_with_delays, 1) if routes_with_delays > 0 else 0,
            "total_delay_minutes": total_delay_minutes
        }
    
    def clear_cache(self):
        """Clear the status cache"""
        self._status_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Real-time status cache cleared")


# Global instance
_realtime_hydration: Optional[RealtimeRouteHydrationService] = None

def get_realtime_hydration() -> RealtimeRouteHydrationService:
    """Get or create global realtime hydration instance"""
    global _realtime_hydration
    if _realtime_hydration is None:
        _realtime_hydration = RealtimeRouteHydrationService()
    return _realtime_hydration
