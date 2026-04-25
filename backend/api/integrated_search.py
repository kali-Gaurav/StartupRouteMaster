"""
Integrated Search and Booking Flow API Endpoints
Complete end-to-end IRCTC-like flow for offline testing
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel, Field
import orjson as json
import logging
from sqlalchemy.orm import Session
from fastapi.responses import ORJSONResponse

from database import SessionLocal, get_db
from database.models import Stop, Trip, Route
from api.dependencies import get_optional_user
from services.search_service import SearchService
from services.booking_service import BookingService
from schemas import (
    SearchRequest, 
    JourneyInfoResponse, 
    DetailedJourneyResponse, 
    BookingConfirmationRequest,
    PassengerInfo
)
from utils.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v2", tags=["integrated-search"])

# store timestamp of search -> used by unlock to compute search_to_unlock_time_ms
SEARCH_TIMESTAMP_CACHE: dict[str, float] = {}

# Request Coalescing Map
_inflight_unified_searches: Dict[str, asyncio.Event] = {}
_unified_search_results: Dict[str, Any] = {}

@router.post("/search/unified", response_model=List[JourneyInfoResponse])
@limiter.limit("30/minute")
async def unified_search(request: Request, search_payload: SearchRequest, db: Session = Depends(get_db)):
    """
    [Task 50.1] V3 Master Orchestrator.
    Integrates Project Shield, Zero-Latency Cache, and Scraper Sentinel.
    """
    from services.fraud_service import fraud_service
    from services.multi_layer_cache import multi_layer_cache, TTL_ROUTE_SEARCH, CACHE_VERSION
    from services.scraper_sentinel import scraper_sentinel
    import time
    import hashlib

    start_time = time.perf_counter()
    
    # [Task 50.1] Metadata Fingerprinting (Project Shield S2)
    fingerprint = request.headers.get("x-device-fingerprint", "GUEST_FP")
    origin_ip = request.client.host
    
    # 1. Block Scrapers/Bots Before CPU Work [45.1]
    if not await fraud_service.validate_identity(db=db, user_id=None, fingerprint=fingerprint, city="UNKNOWN"):
        raise HTTPException(status_code=403, detail="Security Filter: High-risk activity detected.")

    # 2. Canonical V3 Fingerprint [47.1]
    query_str = f"{search_payload.source}:{search_payload.destination}:{search_payload.date}:{CACHE_VERSION}"
    cache_key = f"v3:search:{hashlib.md5(query_str.encode()).hexdigest()}"

    # 3. Dynamic Engine Filtering (Circuit Breaker Awareness) [48.7]
    permitted = search_payload.engine or ["NTES", "RAPID"]
    active_engines = [e for e in permitted if scraper_sentinel.is_available(e.lower())]
    
    if not active_engines and "RAPID" not in permitted:
        raise HTTPException(status_code=503, detail="Circuit Breaker: All search sources temporarily offline.")

    # 4. Zero-Latency Multi-Layer Cache with SWR/Thundering Herd Shield [47.2 & 47.3]
    async def fetch_fresh():
        """Master Orchestrator Worker."""
        search_service = SearchService(db)
        return await search_service.search_routes(
            source=search_payload.source,
            destination=search_payload.destination,
            travel_date=search_payload.date,
            budget_category=search_payload.budget,
            request=request,
            permitted_engines=active_engines,
            discovery_only=search_payload.discovery
        )

    try:
        # [Task 47.3] Probabilistic Background Refresh & Distributed Lock Protection
        response_data = await multi_layer_cache.get_or_set(
            key=cache_key,
            func=fetch_fresh,
            ttl=TTL_ROUTE_SEARCH
        )
        
        latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"🚀 V3 Master Orchestrator: {search_payload.source}->{search_payload.destination} | {latency:.2f}ms")
        
        # [Task 6.1] Background Telemetry (Latency Tracking)
        return response_data
        
    except Exception as e:
        logger.error(f"V3 Orchestrator Failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="V3 Orchestrator: Internal Error during plan generation.")

async def _cleanup_unified_results(key: str):
    await asyncio.sleep(5)
    _unified_search_results.pop(key, None)

@router.get("/journey/{journey_id}/unlock-details")
async def unlock_journey_details(
    journey_id: str,
    travel_date: str = Query(..., description="YYYY-MM-DD"),
    coach_preference: str = "AC_THREE_TIER",
    passenger_age: int = 30,
    concession_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_optional_user)
):
    try:
        from services.journey_cache import get_journey
        from services.seat_verification import SeatVerificationService
        from services.fare_verification import FareVerificationService
        from services.unlock_service import UnlockService
        
        journey = await get_journey(journey_id)
        if not journey:
            raise HTTPException(status_code=404, detail="Journey expired. Please search again.")

        # 1. Concurrent Seat & Fare Verification (Task 2.8)
        seat_service = SeatVerificationService()
        fare_service = FareVerificationService()
        
        seats_task = seat_service.verify_journey(journey)
        fares_task = fare_service.verify_journey_fares(journey, coach_preference)
        
        seats_ok, fares_res = await asyncio.gather(seats_task, fares_task)

        if not seats_ok:
            return {"success": False, "message": "Seats not available for this route."}
        
        # Update journey cost with real-time fare
        journey["total_cost"] = fares_res["total_fare"]

        # 2. Payment/Unlock Check
        is_unlocked = False
        if current_user:
            # Check DB to see if they completed the Payment Session Code flow
            is_unlocked = UnlockService.is_route_unlocked(db, current_user.id, journey_id)
            
        if not is_unlocked:
            # If not paid, return the journey but keep it locked (frontend prompts payment)
            journey["is_locked"] = True
            return {"success": True, "message": "Payment required to view details.", "journey": journey, "requires_payment": True}

        # 3. Unlock Success
        journey["is_locked"] = False
        return {"success": True, "journey": journey}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock Error: {e}")
        raise HTTPException(status_code=500, detail="Unlock failed")

# Rest of the integrated_search.py file...
class PassengerDetail(BaseModel):
    name: str
    age: int
    gender: str # M/F/O
    preference: Optional[str] = "LB"

class ManualBookingRequest(BaseModel):
    journey_id: str
    travel_date: str
    passengers: List[PassengerDetail]
    contact_email: str
    contact_phone: str

@router.post("/booking/confirm_manual")
async def confirm_manual_booking(
    request: ManualBookingRequest, 
    db: Session = Depends(get_db),
    current_user = Depends(get_optional_user)
):
    try:
        from services.booking_queue_service import BookingQueueService
        from services.journey_cache import get_journey
        
        queue_service = BookingQueueService(db)
        passenger_list = [p.dict() for p in request.passengers]
        
        # 1. Fetch Journey Data from Cache
        journey_data = await get_journey(request.journey_id)
        if not journey_data:
            # Fallback for manual reconstruction if cache expired
            journey_data = {
                "source": "Unknown", 
                "destination": "Unknown", 
                "date": request.travel_date,
                "legs": [{"train_number": "MANUAL"}]
            }
        
        # 2. Create Request in Queue
        user_id = current_user.id if current_user else "guest_user"
        booking_req = await queue_service.create_request(
            user_id=user_id,
            journey_data=journey_data,
            passengers=passenger_list,
            phone=request.contact_phone,
            email=request.contact_email
        )
            
        return {
            "success": True, 
            "booking_request_id": str(booking_req.id), 
            "status": "PENDING",
            "message": "Your booking request is in the queue. You will receive a ticket on Telegram/Phone soon."
        }
    except Exception as e:
        logger.error(f"Manual Booking Queue Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Booking request failed to queue")
