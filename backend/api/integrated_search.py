"""
Integrated Search and Booking Flow API Endpoints
Complete end-to-end IRCTC-like flow for offline testing
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import json
import logging

logger = logging.getLogger(__name__)

from backend.database import SessionLocal, get_db
from backend.database.models import Stop, Trip, Route
from backend.services.search_service import SearchService
from backend.schemas import (
    SearchRequest, 
    JourneyInfoResponse, 
    DetailedJourneyResponse, 
    BookingConfirmationRequest,
    PassengerInfo
)
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v2", tags=["integrated-search"])


# ============================================================================
# INTEGRATED SEARCH ENDPOINTS
# ============================================================================

@router.post("/search/unified", response_model=List[JourneyInfoResponse])
async def unified_search(request: SearchRequest, db: Session = Depends(get_db)):
    """
    Complete integrated search returning multiple journey options
    Consolidated into SearchService
    """
    try:
        service = SearchService(db)
        result = await service.search_routes(
            source=request.source,
            destination=request.destination,
            travel_date=request.travel_date
        )
        
        if not result.get("journeys"):
            raise HTTPException(
                status_code=404,
                detail={"message": "No trains available on this route"}
            )
        
        # Returns List[JourneyInfoResponse]
        return result["journeys"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified Search Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/journey/{journey_id}/unlock-details", response_model=DetailedJourneyResponse)
async def unlock_journey_details(
    journey_id: str,
    travel_date: str = Query(..., description="YYYY-MM-DD"),
    coach_preference: str = "AC_THREE_TIER",
    passenger_age: int = 30,
    concession_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> DetailedJourneyResponse:
    """
    Unlock complete journey details with all verifications
    Consolidated into SearchService
    """
    try:
        service = SearchService(db)
        result = await service.unlock_journey_details(
            journey_id=journey_id,
            travel_date_str=travel_date,
            coach_preference=coach_preference,
            passenger_age=passenger_age,
            concession_type=concession_type
        )
        
        if not result.get("journey"):
            raise HTTPException(
                status_code=404,
                detail={"message": result.get("message", "Journey not found")}
            )
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock Details Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unlock journey details")
    
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


@router.get("/status")
async def get_integrated_status() -> Dict:
    """
    Get status of integrated search system
    """
    return {
        "status": "active",
        "engine": "RailwayRouteEngine/v2",
        "features": [
            "GTFS-based search",
            "Real-time verification",
            "Seat allocation",
            "Unified DataProvider"
        ]
    }


