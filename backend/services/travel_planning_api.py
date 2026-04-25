"""
Travel Planning API Endpoints
=============================

This module provides FastAPI endpoints for the travel planning system.
Integrates with the existing backend infrastructure.

Endpoints:
- POST /api/travel/plan - Create travel plan
- GET /api/travel/plan/{plan_id} - Get travel plan
- POST /api/travel/search - Search with filters
- GET /api/station/{code}/amenities - Get station amenities
- POST /api/waiting/book - Book waiting package
- GET /api/crowd/analyze - Get crowd analysis
- POST /api/redistribution/offer - Create redistribution offer

Author: Algorithm Team
Version: 1.0.0
"""
import logging
from typing import Optional, List
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/travel", tags=["travel_planning"])


# =========================================================================
# REQUEST MODELS
# =========================================================================

class TravelPlanRequest(BaseModel):
    """Request model for travel planning"""
    origin: str = Field(..., description="Origin station code", example="NDLS")
    destination: str = Field(..., description="Destination station code", example="BCT")
    travel_date: str = Field(..., description="Travel date (YYYY-MM-DD)", example="2024-12-25")
    passenger_count: int = Field(1, ge=1, le=6, description="Number of passengers")
    
    # Preferences
    preference: str = Field("balanced", description="Travel preference: fastest, cheapest, comfortable, crowd_free, balanced")
    wait_hours: int = Field(6, ge=0, le=24, description="Maximum wait time in hours")
    max_cost: float = Field(10000, ge=0, description="Maximum budget")
    travel_class: str = Field("SL", description="Preferred class: SL, 3A, 2A, 1A, CC")
    
    # Options
    allow_multi_modal: bool = Field(True, description="Allow multi-modal journeys")
    avoid_crowd: bool = Field(True, description="Avoid crowded trains")
    
    # User context
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class WaitingBookingRequest(BaseModel):
    """Request model for waiting package booking"""
    passenger_id: str = Field(..., description="Passenger ID")
    station_code: str = Field(..., description="Station code")
    package_id: str = Field(..., description="Package ID: basic_wait, standard_wait, premium_wait, family_wait, senior_wait")
    start_time: str = Field(..., description="Start time (ISO format)")
    passenger_count: int = Field(1, ge=1, le=6)


class RedistributionOfferRequest(BaseModel):
    """Request model for redistribution offer"""
    passenger_id: str
    booking_id: str
    original_train: str
    alternative_train: str
    incentive_amount: float = 0.0


# =========================================================================
# RESPONSE MODELS
# =========================================================================

class TravelOptionResponse(BaseModel):
    """Travel option in response"""
    option_id: str
    option_type: str
    from_station: str
    to_station: str
    departure_time: Optional[str]
    arrival_time: Optional[str]
    duration_minutes: int
    wait_minutes: int
    wait_station: Optional[str]
    total_fare: float
    comfort_score: float
    crowd_level: str
    crowd_avoidance_score: float
    train_numbers: List[str]
    seat_class: str
    seat_available: bool
    is_recommended: bool
    recommendation_reason: str


class TravelPlanResponse(BaseModel):
    """Travel plan response"""
    plan_id: str
    origin: str
    destination: str
    travel_date: str
    passenger_count: int
    options: List[TravelOptionResponse]
    recommended: Optional[TravelOptionResponse]
    fastest: Optional[TravelOptionResponse]
    cheapest: Optional[TravelOptionResponse]
    generated_at: str
    valid_until: str


class StationAmenitiesResponse(BaseModel):
    """Station amenities response"""
    station: str
    amenities: List[dict]
    summary: dict


class CrowdAnalysisResponse(BaseModel):
    """Crowd analysis response"""
    stations: dict
    opportunities: List[dict]
    timestamp: str


# =========================================================================
# API ENDPOINTS
# =========================================================================

@router.post("/plan", response_model=TravelPlanResponse)
async def create_travel_plan(
    request: TravelPlanRequest,
    db: Session = Depends(lambda: None)  # Would use actual dependency
):
    """
    Create a complete travel plan with multiple options.
    
    This endpoint provides:
    - Multiple travel options (direct, wait, alternative, multi-modal)
    - Crowd level information for each option
    - Comfort scores
    - Pricing breakdown
    - Recommendations
    
    Example request:
    ```json
    {
        "origin": "NDLS",
        "destination": "BCT",
        "travel_date": "2024-12-25",
        "passenger_count": 2,
        "preference": "balanced",
        "wait_hours": 4,
        "max_cost": 5000
    }
    ```
    """
    try:
        # Parse date
        travel_date = datetime.strptime(request.travel_date, "%Y-%m-%d").date()
        
        # Import and create planner
        from services.unified_travel_planner import (
            UnifiedTravelPlanner, TravelRequest, TravelPreference, WaitPreference
        )
        
        # Convert preference
        pref_map = {
            'fastest': TravelPreference.FASTEST,
            'cheapest': TravelPreference.CHEAPEST,
            'comfortable': TravelPreference.COMFORTABLE,
            'crowd_free': TravelPreference.CROWD_FREE,
            'balanced': TravelPreference.BALANCED
        }
        
        # Create travel request
        travel_request = TravelRequest(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            travel_date=travel_date,
            passenger_count=request.passenger_count,
            travel_preference=pref_map.get(request.preference, TravelPreference.BALANCED),
            wait_preference=WaitPreference.ANY_WAIT if request.wait_hours > 0 else WaitPreference.NO_WAIT,
            max_wait_hours=request.wait_hours,
            max_cost=request.max_cost,
            preferred_class=request.travel_class,
            allow_multi_modal=request.allow_multi_modal,
            avoid_high_crowd=request.avoid_crowd,
            user_id=request.user_id
        )
        
        # Create planner and generate plan
        planner = UnifiedTravelPlanner(db)
        plan = await planner.create_travel_plan(travel_request)
        
        # Convert to response
        return TravelPlanResponse(
            plan_id=plan.plan_id,
            origin=plan.request.origin,
            destination=plan.request.destination,
            travel_date=plan.request.travel_date.isoformat(),
            passenger_count=plan.request.passenger_count,
            options=[TravelOptionResponse(**o.to_dict()) for o in plan.options],
            recommended=TravelOptionResponse(**plan.get_recommended().to_dict()) if plan.get_recommended() else None,
            fastest=TravelOptionResponse(**plan.fastest_option.to_dict()) if plan.fastest_option else None,
            cheapest=TravelOptionResponse(**plan.cheapest_option.to_dict()) if plan.cheapest_option else None,
            generated_at=plan.generated_at.isoformat(),
            valid_until=plan.valid_until.isoformat() if plan.valid_until else ""
        )
        
    except Exception as e:
        logger.error(f"Travel plan creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create travel plan: {str(e)}")


@router.get("/plan/{plan_id}")
async def get_travel_plan(plan_id: str):
    """Get a previously created travel plan"""
    # This would retrieve from cache/database
    raise HTTPException(status_code=404, detail="Plan not found or expired")


@router.get("/station/{station_code}/amenities", response_model=StationAmenitiesResponse)
async def get_station_amenities(station_code: str):
    """
    Get amenities available at a station.
    
    Returns:
    - Waiting lounges
    - Food courts
    - Charging stations
    - WiFi availability
    - Language learning (free)
    - Medical assistance
    """
    try:
        from services.station_amenity_service import get_station_amenity_service
        
        amenity_service = get_station_amenity_service()
        result = await amenity_service.get_station_amenities(station_code.upper())
        
        return StationAmenitiesResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to get amenities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/waiting/book")
async def book_waiting_package(request: WaitingBookingRequest):
    """
    Book a waiting package at a station.
    
    Packages:
    - basic_wait: ₹50/2hr - Basic seating
    - standard_wait: ₹200/3hr - AC lounge with snacks
    - premium_wait: ₹500/4hr - Luxury lounge with meals
    - family_wait: ₹400/4hr - Family-friendly
    - senior_wait: ₹250/4hr - Senior citizen friendly
    """
    try:
        from services.station_amenity_service import get_station_amenity_service
        
        amenity_service = get_station_amenity_service()
        
        start_time = datetime.fromisoformat(request.start_time)
        
        booking = await amenity_service.book_waiting(
            passenger_id=request.passenger_id,
            station_code=request.station_code.upper(),
            package_id=request.package_id,
            start_time=start_time,
            passenger_count=request.passenger_count
        )
        
        return {
            'status': 'success',
            'booking_id': booking.booking_id,
            'amount_paid': booking.amount_paid,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Waiting booking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crowd/analyze", response_model=CrowdAnalysisResponse)
async def analyze_crowd():
    """
    Analyze crowd levels across the network.
    
    Returns:
    - Current crowd levels at major stations
    - Redistribution opportunities
    - Predictions
    """
    try:
        from services.crowd_control_service import get_crowd_control_service
        
        crowd_service = get_crowd_control_service()
        analysis = await crowd_service.analyze_network_demand()
        
        return CrowdAnalysisResponse(**analysis)
        
    except Exception as e:
        logger.error(f"Crowd analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redistribution/offer")
async def create_redistribution_offer(request: RedistributionOfferRequest):
    """
    Create a redistribution offer for a passenger.
    
    This is used when a train is overcrowded and we want to
    move passengers to less crowded alternatives.
    """
    try:
        from services.crowd_control_service import get_crowd_control_service
        
        crowd_service = get_crowd_control_service()
        
        offer = await crowd_service.create_redistribution_offer(
            passenger_id=request.passenger_id,
            original_booking_id=request.booking_id,
            original_train=request.original_train,
            alternative_train=request.alternative_train,
            incentive_amount=request.incentive_amount
        )
        
        return {
            'offer_id': offer.offer_id,
            'original_train': offer.original_train,
            'alternative_train': offer.alternative_train,
            'incentive': offer.incentive_amount,
            'expires_at': offer.expires_at.isoformat() if offer.expires_at else None
        }
        
    except Exception as e:
        logger.error(f"Redistribution offer failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multimodal/search")
async def search_multimodal(
    origin: str = Query(..., description="Origin station"),
    destination: str = Query(..., description="Destination station"),
    travel_date: str = Query(..., description="Travel date"),
    passenger_count: int = Query(1, ge=1, le=6),
    max_cost: float = Query(10000, ge=0)
):
    """
    Search for multi-modal journeys (train + bus, train + flight, etc.)
    """
    try:
        from services.multimodal_planning_service import (
            get_multimodal_planning_service,
            JourneySearchRequest,
            ComfortLevel
        )
        from datetime import date as date_type
        
        travel_date_obj = date_type.fromisoformat(travel_date)
        
        multimodal = get_multimodal_planning_service()
        
        request = JourneySearchRequest(
            origin=origin.upper(),
            destination=destination.upper(),
            travel_date=travel_date_obj,
            passenger_count=passenger_count,
            max_cost=max_cost,
            comfort_preference=ComfortLevel.STANDARD
        )
        
        journeys = await multimodal.search_journeys(request)
        
        return {
            'status': 'success',
            'journeys': [
                {
                    'journey_id': j.journey_id,
                    'journey_type': j.journey_type.value,
                    'total_duration': j.total_duration_minutes,
                    'total_fare': j.total_fare,
                    'comfort_score': j.comfort_score,
                    'segments': [
                        {
                            'mode': s.mode,
                            'from': s.from_location,
                            'to': s.to_location,
                            'fare': s.fare
                        }
                        for s in j.segments
                    ]
                }
                for j in journeys[:5]
            ]
        }
        
    except Exception as e:
        logger.error(f"Multi-modal search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# HEALTH CHECK
# =========================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "travel_planning",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# Export router
__all__ = ['router']