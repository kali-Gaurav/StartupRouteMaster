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
router = APIRouter(prefix="/api/v2", tags=["integrated-search"])

# store timestamp of search -> used by unlock to compute search_to_unlock_time_ms
SEARCH_TIMESTAMP_CACHE: dict[str, float] = {}

# Request Coalescing Map
_inflight_unified_searches: Dict[str, asyncio.Event] = {}
_unified_search_results: Dict[str, Any] = {}

@router.post("/search/unified", response_model=List[JourneyInfoResponse])
@limiter.limit("30/minute")
async def unified_search(request: Request, search_payload: SearchRequest, db: Session = Depends(get_db)):
    """
    Production-grade Unified Multi-Modal Search (V2).
    Optimized with Single-Flight Coalescing, Pareto-Ranking, and Redis Caching.
    """
    from core.unified_planner import UnifiedPlanner
    from adapters.train_adapter import TrainAdapter
    from schemas.unified_search import UnifiedSearchRequest
    import time

    start_time = time.perf_counter()
    cache_key = f"unified_v3:{search_payload.source.upper()}:{search_payload.destination.upper()}:{search_payload.date}"

    # 1. Request Coalescing
    if cache_key in _inflight_unified_searches:
        logger.info(f"⚡ COALESCE: Joining unified search for {cache_key}")
        await _inflight_unified_searches[cache_key].wait()
        return _unified_search_results.get(cache_key)

    # 2. Check Cache
    from core.redis import async_redis_client
    try:
        cached = await async_redis_client.get(cache_key)
        if cached:
            logger.info(f"✅ CACHE HIT (Hot Path): {cache_key}")
            return ORJSONResponse(content=json.loads(cached))
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")

    # Register in-flight search after cache check fails
    _inflight_unified_searches[cache_key] = asyncio.Event()

    try:
        # 3. Execute Engines via Orchestrator
        unified_req = UnifiedSearchRequest(
            source=search_payload.source,
            destination=search_payload.destination,
            date=search_payload.date,
            preferences="balanced"
        )
        
        search_service = SearchService(db)
        train_adapter = TrainAdapter(search_service)
        planner = UnifiedPlanner(adapters=[train_adapter])
        
        results = await planner.plan(unified_req)
        
        # 4. Map results
        response_data = []
        from services.journey_cache import save_journey
        
        for opt in results:
            legs = [{
                "mode": s.mode, "from": s.from_station, "to": s.to_station,
                "departure": s.departure, "arrival": s.arrival,
                "duration_min": s.duration_minutes, "cost": s.price,
                "train_number": s.train_number, "train_name": s.train_name
            } for s in opt.segments]
            
            journey_dict = {
                "journey_id": opt.journey_id, "total_cost": opt.total_price,
                "total_duration": opt.total_duration, "safety_score": opt.safety_score,
                "legs": legs, "segments": [s.dict() for s in opt.segments],
                "is_locked": opt.is_locked
            }
            await save_journey(opt.journey_id, journey_dict)
            response_data.append(journey_dict)

        # 5. Store in Cache
        try:
            await async_redis_client.setex(cache_key, 300, json.dumps(response_data))
        except Exception:
            pass

        _unified_search_results[cache_key] = response_data
        return response_data
        
    except Exception as e:
        logger.error(f"Unified Search Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Signal and Cleanup
        event = _inflight_unified_searches.pop(cache_key, None)
        if event:
            event.set()
        asyncio.create_task(_cleanup_unified_results(cache_key))

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
        from services.unlock_service import UnlockService
        
        journey = await get_journey(journey_id)
        if not journey:
            raise HTTPException(status_code=404, detail="Journey expired. Please search again.")

        # 1. Seat Verification
        seat_service = SeatVerificationService()
        seats_ok = await seat_service.verify_journey(journey)

        if not seats_ok:
            return {"success": False, "message": "Seats not available for this route."}

        # 2. Payment/Unlock Check
        is_unlocked = False
        if current_user:
            unlock_service = UnlockService(db)
            # Check DB to see if they completed the Payment Session Code flow
            is_unlocked = await unlock_service.is_route_unlocked(current_user.id, journey_id)
            
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
