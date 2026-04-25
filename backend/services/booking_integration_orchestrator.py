"""
Booking Integration Orchestrator
Unified service that orchestrates all booking-related integrations:
- Pricing calculation
- Delay-aware routing
- Real-time status hydration
- Seat allocation

This is the main entry point for the complete booking flow.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from dataclasses import dataclass

logger = logging.getLogger("booking.orchestrator")

@dataclass
class BookingRequest:
    """Complete booking request with all details"""
    user_id: str
    source: str
    destination: str
    travel_date: date
    passengers: List[Dict[str, Any]]
    train_number: Optional[str] = None
    train_class: str = "SL"
    quota: str = "GN"
    session_id: Optional[str] = None

@dataclass
class BookingQuote:
    """Complete booking quote with all calculations"""
    # Price breakdown
    base_fare: float
    dynamic_surge: float
    surge_multiplier: float
    platform_fee: float
    total: float
    
    # Delay information
    predicted_delays: Dict[str, int]
    delay_warnings: List[str]
    
    # Availability
    seat_availability: str  # "available", "rac", "waitlist"
    waitlist_position: Optional[int] = None
    
    # Seat assignments (if confirmed)
    seat_assignments: Optional[List[Dict]] = None
    
    # Validity
    quote_valid_until: datetime
    route_is_viable: bool = True


class BookingIntegrationOrchestrator:
    """
    Orchestrates all booking integrations into a unified flow.
    
    Flow:
    1. Calculate price (with dynamic surge)
    2. Check real-time availability
    3. Apply delay predictions
    4. Allocate seats
    5. Generate quote
    """
    
    QUOTE_VALIDITY_MINUTES = 15
    
    def __init__(self, db=None):
        self.db = db
        self._price_calculator = None
        self._delay_aware_routing = None
        self._realtime_hydration = None
        self._seat_allocator = None
    
    def _get_price_calculator(self):
        """Lazy load price calculator"""
        if self._price_calculator is None:
            from services.booking_price_calculator import BookingPriceCalculator
            self._price_calculator = BookingPriceCalculator(self.db)
        return self._price_calculator
    
    def _get_delay_aware_routing(self):
        """Lazy load delay-aware routing"""
        if self._delay_aware_routing is None:
            from services.delay_aware_routing import DelayAwareRoutingService
            self._delay_aware_routing = DelayAwareRoutingService()
        return self._delay_aware_routing
    
    def _get_realtime_hydration(self):
        """Lazy load realtime hydration"""
        if self._realtime_hydration is None:
            from services.realtime_route_hydration import RealtimeRouteHydrationService
            self._realtime_hydration = RealtimeRouteHydrationService()
        return self._realtime_hydration
    
    def _get_seat_allocator(self):
        """Lazy load seat allocator"""
        if self._seat_allocator is None:
            from services.booking_seat_allocator import BookingSeatAllocator
            self._seat_allocator = BookingSeatAllocator(self.db)
        return self._seat_allocator
    
    async def generate_booking_quote(
        self,
        request: BookingRequest
    ) -> BookingQuote:
        """
        Generate complete booking quote with all integrations.
        
        This is the main entry point for the booking flow.
        """
        logger.info(f"Generating booking quote for {request.user_id} from {request.source} to {request.destination}")
        
        try:
            # Step 1: Calculate price with dynamic surge
            price_breakdown = await self._calculate_price(request)
            
            # Step 2: Get delay predictions
            delay_info = await self._get_delay_predictions(request)
            
            # Step 3: Check real-time availability
            availability = await self._check_availability(request)
            
            # Step 4: Attempt seat allocation
            seat_allocation = await self._allocate_seats(request)
            
            # Step 5: Generate warnings
            warnings = self._generate_warnings(delay_info, availability, seat_allocation)
            
            # Determine if route is viable
            is_viable = (
                availability != "cancelled" and 
                not seat_allocation.success or seat_allocation.waitlist_position is None
            )
            
            # Create quote
            quote = BookingQuote(
                base_fare=price_breakdown.base_fare,
                dynamic_surge=price_breakdown.dynamic_surge,
                surge_multiplier=price_breakdown.surge_multiplier,
                platform_fee=price_breakdown.platform_fee,
                total=price_breakdown.total,
                predicted_delays=delay_info,
                delay_warnings=warnings,
                seat_availability=availability,
                waitlist_position=seat_allocation.waitlist_position,
                seat_assignments=seat_allocation.seats if seat_allocation.success else None,
                quote_valid_until=datetime.utcnow() + timedelta(minutes=self.QUOTE_VALIDITY_MINUTES),
                route_is_viable=is_viable
            )
            
            logger.info(f"Quote generated: ₹{quote.total} ({availability})")
            return quote
            
        except Exception as e:
            logger.error(f"Quote generation failed: {e}")
            raise
    
    async def _calculate_price(self, request: BookingRequest):
        """Calculate booking price with dynamic surge"""
        calculator = self._get_price_calculator()
        
        return await calculator.calculate_booking_price(
            source=request.source,
            destination=request.destination,
            travel_date=request.travel_date,
            passenger_count=len(request.passengers),
            train_class=request.train_class,
            user_id=request.user_id
        )
    
    async def _get_delay_predictions(self, request: BookingRequest) -> Dict[str, int]:
        """Get delay predictions for the route"""
        delay_service = self._get_delay_aware_routing()
        
        delays = {}
        
        if request.train_number:
            # Single train
            delay_info = await delay_service.predict_leg_delay(
                request.train_number,
                request.travel_date
            )
            delays[request.train_number] = int(delay_info.predicted_delay_minutes)
        else:
            # Would need route info - return empty for now
            pass
        
        return delays
    
    async def _check_availability(self, request: BookingRequest) -> str:
        """Check real-time seat availability"""
        # Simplified - would integrate with actual availability API
        # For now, return mock based on class
        availability_map = {
            "1A": "available",
            "2A": "available", 
            "3A": "available",
            "SL": "available",
            "CC": "available"
        }
        return availability_map.get(request.train_class, "available")
    
    async def _allocate_seats(self, request: BookingRequest):
        """Allocate seats for passengers"""
        allocator = self._get_seat_allocator()
        
        if not request.train_number:
            # Can't allocate without train
            from services.booking_seat_allocator import BookingSeatAllocation
            return BookingSeatAllocation(
                success=False,
                message="Train not specified"
            )
        
        return await allocator.allocate_seats_for_booking(
            train_number=request.train_number,
            travel_date=datetime.combine(request.travel_date, datetime.min.time()),
            passengers=request.passengers,
            train_class=request.train_class,
            quota=request.quota
        )
    
    def _generate_warnings(
        self,
        delay_info: Dict[str, int],
        availability: str,
        seat_allocation
    ) -> List[str]:
        """Generate user-facing warnings"""
        warnings = []
        
        # Delay warnings
        for train, delay in delay_info.items():
            if delay > 30:
                warnings.append(f"Train {train} expected delay: {delay} minutes")
            elif delay > 0:
                warnings.append(f"Train {train} may be delayed by ~{delay} minutes")
        
        # Availability warnings
        if availability == "waitlist":
            warnings.append("Current status: Waitlist - confirmation not guaranteed")
        elif availability == "rac":
            warnings.append("Current status: RAC - partial confirmation expected")
        
        # Seat allocation warnings
        if seat_allocation.waitlist_position:
            warnings.append(f"Waitlist position: {seat_allocation.waitlist_position}")
        
        return warnings
    
    async def confirm_booking(
        self,
        quote: BookingQuote,
        request: BookingRequest
    ) -> Dict[str, Any]:
        """
        Confirm booking after quote acceptance.
        This would integrate with the actual booking service.
        """
        # This is a placeholder - actual implementation would:
        # 1. Lock the quote price
        # 2. Call booking_service.create_booking()
        # 3. Process payment
        # 4. Generate PNR
        # 5. Send confirmation
        
        return {
            "status": "pending",
            "message": "Booking confirmation would proceed here",
            "quote": quote.to_dict() if hasattr(quote, 'to_dict') else str(quote)
        }


# Convenience function for quick integration
async def quick_quote(
    source: str,
    destination: str,
    travel_date: date,
    passenger_count: int,
    train_class: str = "SL",
    user_id: str = "anonymous"
) -> Dict[str, Any]:
    """
    Quick quote generation without full booking request object.
    Useful for price estimation without committing to a specific train.
    """
    request = BookingRequest(
        user_id=user_id,
        source=source,
        destination=destination,
        travel_date=travel_date,
        passengers=[{"id": f"pax_{i}"} for i in range(passenger_count)],
        train_class=train_class
    )
    
    orchestrator = BookingIntegrationOrchestrator()
    quote = await orchestrator.generate_booking_quote(request)
    
    return {
        "source": source,
        "destination": destination,
        "travel_date": travel_date.isoformat(),
        "passengers": passenger_count,
        "class": train_class,
        "price": {
            "base": quote.base_fare,
            "surge": quote.dynamic_surge,
            "fee": quote.platform_fee,
            "total": quote.total,
            "multiplier": quote.surge_multiplier
        },
        "valid_until": quote.quote_valid_until.isoformat(),
        "warnings": quote.delay_warnings
    }


# Global instance
_orchestrator: Optional[BookingIntegrationOrchestrator] = None

def get_booking_orchestrator(db=None) -> BookingIntegrationOrchestrator:
    """Get or create global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = BookingIntegrationOrchestrator(db)
    return _orchestrator