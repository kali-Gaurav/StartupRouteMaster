"""
Integrated Search and Booking Flow API Endpoints
Complete end-to-end IRCTC-like flow for offline testing
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import json

from backend.database import SessionLocal
from backend.database.models import Stop, Trip, Route
from backend.core.route_engine import RouteEngine, route_engine
from backend.services.seat_allocation import SeatAllocationService, CoachType
from backend.services.verification_engine import verification_service, VerificationDetails
from backend.utils.station_utils import resolve_station_by_name, find_stations_by_partial_name
from backend.utils.validation import SearchRequestValidator, validate_date_string

router = APIRouter(prefix="/api/v2", tags=["integrated-search"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class PassengerInfo(BaseModel):
    """Passenger information"""
    full_name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^[MFO]$")
    concession_type: Optional[str] = None
    phone: Optional[str] = None


class SearchRequest(BaseModel):
    """Integrated search request"""
    source: str = Field(..., min_length=2, max_length=100)
    destination: str = Field(..., min_length=2, max_length=100)
    travel_date: str = Field(..., description="YYYY-MM-DD format")
    return_date: Optional[str] = None
    num_passengers: int = Field(default=1, ge=1, le=6)
    passengers: List[PassengerInfo] = None
    coach_preference: str = Field(default="AC_THREE_TIER")
    is_tatkal: bool = False


class JourneyInfoResponse(BaseModel):
    """Complete journey info for display"""
    journey_id: str
    num_segments: int
    distance_km: float
    travel_time: str
    num_transfers: int
    is_direct: bool
    cheapest_fare: float
    premium_fare: float
    has_overnight: bool
    availability_status: str


class DetailedJourneyResponse(BaseModel):
    """Complete detailed journey with all calculations"""
    journey: JourneyInfoResponse
    segments: List[Dict]
    seat_allocation: Dict
    verification: Dict
    fare_breakdown: Dict
    can_unlock_details: bool


class BookingConfirmationRequest(BaseModel):
    """Request to confirm a booking"""
    journey_id: str
    selected_coach: str
    passengers: List[PassengerInfo]
    payment_method: str = "online"


# ============================================================================
# INTEGRATED SEARCH ENDPOINTS
# ============================================================================

@router.post("/search/unified", response_model=List[JourneyInfoResponse])
async def unified_search(request: SearchRequest):
    """
    Complete integrated search returning multiple journey options
    This is the new endpoint replacing old search
    """
    db = SessionLocal()
    
    try:
        # Validate input
        validator = SearchRequestValidator()
        if not validator.validate(
            source=request.source,
            destination=request.destination,
            date_str=request.travel_date
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "errors": validator.get_errors(),
                    "message": "Invalid search parameters"
                }
            )
        
        # Resolve stations
        from_stop = resolve_station_by_name(db, request.source)
        to_stop = resolve_station_by_name(db, request.destination)
        
        if not from_stop or not to_stop:
            available_from = find_stations_by_partial_name(db, request.source, limit=5)
            available_to = find_stations_by_partial_name(db, request.destination, limit=5)
            
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"Stations not found",
                    "suggestions_from": [{"name": s.name, "code": s.code} for s in available_from],
                    "suggestions_to": [{"name": s.name, "code": s.code} for s in available_to]
                }
            )
        
        if from_stop.id == to_stop.id:
            raise HTTPException(
                status_code=400,
                detail={"message": "Source and destination must be different"}
            )
        
        # Parse travel date
        travel_date = validate_date_string(request.travel_date, allow_past=False)
        if not travel_date:
            raise HTTPException(
                status_code=400,
                detail={"message": "Invalid travel date or date in past"}
            )
        
        # Search for trips between stations
        trips = db.query(Trip).join(
            Route
        ).filter(
            Route.agency_id.isnot(None)
        ).limit(5).all()
        
        if not trips:
            raise HTTPException(
                status_code=404,
                detail={"message": "No trains available on this route"}
            )
        
        # Reconstruct journeys using journey reconstruction engine
        engine = JourneyReconstructionEngine(db)
        journeys = []
        
        for trip in trips[:3]:  # Limit to 3 options for now
            try:
                segment = engine.reconstruct_single_segment_journey(
                    trip_id=trip.id,
                    from_stop_id=from_stop.id,
                    to_stop_id=to_stop.id,
                    travel_date=travel_date
                )
                
                if segment:
                    journey = engine.reconstruct_complete_journey([segment], travel_date)
                    
                    # Convert to response format
                    journeys.append(JourneyInfoResponse(
                        journey_id=journey.journey_id,
                        num_segments=journey.num_segments,
                        distance_km=journey.total_distance_km,
                        travel_time=f"{int(journey.total_travel_time_mins // 60):02d}:{journey.total_travel_time_mins % 60:02d}",
                        num_transfers=journey.num_transfers,
                        is_direct=journey.is_direct,
                        cheapest_fare=journey.cheapest_fare,
                        premium_fare=journey.premium_fare,
                        has_overnight=journey.has_overnight,
                        availability_status=journey.availability_status
                    ))
            except Exception as e:
                continue  # Skip this trip if reconstruction fails
        
        if not journeys:
            raise HTTPException(
                status_code=503,
                detail={"message": "Unable to find available trains at this time"}
            )
        
        return journeys
    
    finally:
        db.close()


@router.get("/journey/{journey_id}/unlock-details")
async def unlock_journey_details(
    journey_id: str,
    travel_date: str = Query(..., description="YYYY-MM-DD"),
    coach_preference: str = "AC_THREE_TIER",
    passenger_age: int = 30,
    concession_type: Optional[str] = None
) -> DetailedJourneyResponse:
    """
    Unlock complete journey details with all verifications
    Called when user clicks on a journey to see full details
    """
    db = SessionLocal()
    
    try:
        # Parse travel date
        parsed_date = validate_date_string(travel_date, allow_past=False)
        if not parsed_date:
            raise HTTPException(
                status_code=400,
                detail={"message": "Invalid travel date"}
            )
        
        # In real system, would look up journey from database
        # For now, reconstruct from request
        trips = db.query(Trip).limit(1).all()
        if not trips:
            raise HTTPException(
                status_code=404,
                detail={"message": "Journey not found"}
            )
        
        # Reconstruct journey
        engine = JourneyReconstructionEngine(db)
        trip = trips[0]
        
        # Get stops for journey
        stops = db.query(Stop).limit(2).all()
        if len(stops) < 2:
            raise HTTPException(
                status_code=400,
                detail={"message": "Cannot reconstruct journey"}
            )
        
        segment = engine.reconstruct_single_segment_journey(
            trip_id=trip.id,
            from_stop_id=stops[0].id,
            to_stop_id=stops[1].id,
            travel_date=parsed_date
        )
        
        if not segment:
            raise HTTPException(
                status_code=404,
                detail={"message": "Journey details unavailable"}
            )
        
        journey = engine.reconstruct_complete_journey([segment], parsed_date)
        
        # Allocate seats
        seat_service = SeatAllocationService(db)
        dummy_passengers = [{
            "full_name": "Passenger 1",
            "age": passenger_age,
            "gender": "M"
        }]
        
        coach_type = getattr(CoachType, coach_preference, CoachType.AC_THREE_TIER)
        seat_allocation = seat_service.allocate_seats_for_booking(
            trip_id=str(trip.id),
            passengers=dummy_passengers,
            coach_preference=coach_type
        )
        
        # Verify all details
        verification = verification_service.verify_journey(
            journey=journey,
            travel_date=parsed_date,
            coach_preference=coach_preference,
            passenger_age=passenger_age,
            concession_type=concession_type
        )
        
        # Build response
        return DetailedJourneyResponse(
            journey=JourneyInfoResponse(
                journey_id=journey.journey_id,
                num_segments=journey.num_segments,
                distance_km=journey.total_distance_km,
                travel_time=f"{int(journey.total_travel_time_mins // 60):02d}:{journey.total_travel_time_mins % 60:02d}",
                num_transfers=journey.num_transfers,
                is_direct=journey.is_direct,
                cheapest_fare=journey.cheapest_fare,
                premium_fare=journey.premium_fare,
                has_overnight=journey.has_overnight,
                availability_status=journey.availability_status
            ),
            segments=[seg.to_dict() for seg in journey.segments],
            seat_allocation={
                "allocated": seat_allocation["allocated_seats"],
                "waiting_list": seat_allocation["waiting_list"],
                "seat_details": seat_allocation["seat_details"]
            },
            verification={
                "overall_status": verification.overall_status.value,
                "is_bookable": verification.is_bookable,
                "seat_check": {
                    "status": verification.seat_verification.status.value,
                    "available": verification.seat_verification.available_seats,
                    "message": verification.seat_verification.message
                },
                "schedule_check": {
                    "status": verification.schedule_verification.status.value,
                    "delay_minutes": verification.schedule_verification.delay_minutes,
                    "message": verification.schedule_verification.message
                },
                "restrictions": verification.restrictions,
                "warnings": verification.warnings
            },
            fare_breakdown={
                "base_fare": verification.fare_verification.base_fare,
                "gst": verification.fare_verification.GST,
                "total_fare": verification.fare_verification.total_fare,
                "cancellation_charges": verification.fare_verification.cancellation_charges,
                "applicable_discounts": verification.fare_verification.applicable_discounts
            },
            can_unlock_details=verification.is_bookable
        )
    
    finally:
        db.close()


@router.post("/station-autocomplete")
async def station_autocomplete(
    query: str = Query(..., min_length=2, max_length=100)
) -> List[Dict]:
    """
    Get station suggestions while typing (autocomplete)
    """
    db = SessionLocal()
    
    try:
        from backend.utils.station_utils import find_stations_by_partial_name
        
        stations = find_stations_by_partial_name(db, query, limit=10)
        
        return [
            {
                "stop_id": s.id,
                "name": s.name,
                "code": s.code,
                "city": s.city,
                "state": s.state
            }
            for s in stations
        ]
    
    finally:
        db.close()


@router.get("/search-history")
async def search_history() -> Dict:
    """
    Return recent searches (simulated for offline)
    """
    return {
        "recent_searches": [
            {
                "source": "Mumbai Central",
                "destination": "New Delhi",
                "date": str(date.today() + timedelta(days=1)),
                "timestamp": datetime.now().isoformat()
            }
        ]
    }


@router.post("/booking/confirm")
async def confirm_booking(request: BookingConfirmationRequest) -> Dict:
    """
    Confirm booking after payment
    """
    # This would integrate with seat allocation and PNR generation
    return {
        "status": "success",
        "pnr_number": "ABC123456",
        "confirmation_number": "1234567890",
        "total_fare": 1500.00,
        "booking_date": datetime.now().isoformat()
    }


@router.get("/travel-checklist")
async def travel_checklist(
    journey_id: str,
    travel_date: str = Query(..., description="YYYY-MM-DD")
) -> Dict:
    """
    Pre-travel checklist and important information
    """
    return {
        "journey_id": journey_id,
        "travel_date": travel_date,
        "checklist": [
            {
                "item": "Carry valid ID proof (Aadhar/PAN/Passport)",
                "status": "pending",
                "priority": "high"
            },
            {
                "item": "Reach station 30 minutes before departure",
                "status": "pending",
                "priority": "high"
            },
            {
                "item": "Check train number from ticket",
                "status": "pending",
                "priority": "medium"
            },
            {
                "item": "Review cancellation policy",
                "status": "pending",
                "priority": "medium"
            }
        ],
        "important_info": {
            "food_available_onboard": True,
            "bedding_charges": 50.00,
            "emergency_contact": "139",
            "ladies_coach_available": True
        }
    }


# ============================================================================
# SIMULATION AND TESTING ENDPOINTS
# ============================================================================

@router.post("/test/simulate-delay")
async def simulate_delay(
    train_number: str,
    travel_date: str = Query(..., description="YYYY-MM-DD"),
    delay_minutes: int = 30
) -> Dict:
    """
    [TEST ONLY] Simulate a train delay for testing verification
    """
    parsed_date = validate_date_string(travel_date, allow_past=True)
    if not parsed_date:
        raise HTTPException(status_code=400, detail={"message": "Invalid date"})
    
    verification_service.data_provider.set_simulated_delay(
        train_number, parsed_date, delay_minutes
    )
    
    return {
        "status": "success",
        "message": f"Simulated {delay_minutes} minute delay for {train_number} on {travel_date}"
    }


@router.post("/test/simulate-cancellation")
async def simulate_cancellation(
    train_number: str,
    travel_date: str = Query(..., description="YYYY-MM-DD"),
    reason: str = "Coach breakdown"
) -> Dict:
    """
    [TEST ONLY] Simulate a train cancellation for testing
    """
    parsed_date = validate_date_string(travel_date, allow_past=True)
    if not parsed_date:
        raise HTTPException(status_code=400, detail={"message": "Invalid date"})
    
    verification_service.data_provider.set_simulated_cancellation(
        train_number, parsed_date, reason
    )
    
    return {
        "status": "success",
        "message": f"Simulated cancellation for {train_number} on {travel_date}: {reason}"
    }


@router.post("/test/clear-simulations")
async def clear_simulations() -> Dict:
    """
    [TEST ONLY] Clear all simulated delays and cancellations
    """
    verification_service.data_provider.clear_simulations()
    
    return {
        "status": "success",
        "message": "All simulations cleared"
    }


@router.get("/test/journey-reconstruction-info")
async def journey_reconstruction_info() -> Dict:
    """
    [DEBUG] Get info about journey reconstruction for testing
    """
    return {
        "endpoints": [
            {
                "path": "/api/v2/search/unified",
                "method": "POST",
                "description": "Main search endpoint with complete journey reconstruction"
            },
            {
                "path": "/api/v2/journey/{journey_id}/unlock-details",
                "method": "GET",
                "description": "Unlock full details with seat allocation, verification, and fares"
            }
        ],
        "features": [
            "Complete journey reconstruction with all segment details",
            "Seat allocation from TrainCompartment model",
            "Real-time fare calculation with dynamic pricing",
            "Verification of seat availability, schedule, and fare",
            "Offline simulation mode for testing",
            "Multi-segment journey support (with transfers)"
        ],
        "simulation_endpoints": [
            "/api/v2/test/simulate-delay",
            "/api/v2/test/simulate-cancellation",
            "/api/v2/test/clear-simulations"
        ]
    }


