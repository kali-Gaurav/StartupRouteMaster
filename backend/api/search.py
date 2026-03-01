from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from database import get_db
from schemas import SearchRequestSchema
from core.route_engine import route_engine
from database.models import Stop, Disruption
from services.station_service import StationService
from services.search_service import SearchService
from database.config import Config
from utils.limiter import limiter
from utils.metrics import SEARCH_LATENCY_SECONDS, SEARCH_REQUESTS_TOTAL, ROUTE_LATENCY_MS
from utils.validation import validate_date_string
from fastapi_cache.decorator import cache
from api.websockets import manager as websocket_manager

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

@router.post("/")
@limiter.limit("60/minute")
@cache(expire=300) # 5 minute cache
async def search_routes_endpoint(
    request: Request, 
    search_request: SearchRequestSchema, 
    db: Session = Depends(get_db),
    dry_run: bool = Query(False, description="If true, only resolve stations and validate without running engine"),
    offset: int = Query(0, ge=0),
    limit: int = Query(15, ge=1, le=50)
):
    """
    Search for routes using the unified Stop (GTFS) model.
    """
    start_time = time.time()
    status_label = "failure"

    try:
        travel_date_str = search_request.date or datetime.now().strftime("%Y-%m-%d")
        if not validate_date_string(travel_date_str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid travel date format. Use YYYY-MM-DD."
            )

        # Unified SearchService handles the engine call
        service = SearchService(db)

        # --- DRY RUN MODE (Topic 3) ---
        if dry_run:
            from utils.station_utils import resolve_stations
            src_stop, dst_stop = resolve_stations(db, search_request.source, search_request.destination)
            
            return {
                "dry_run": True,
                "resolved": {
                    "source": {"code": src_stop.code, "name": src_stop.name} if src_stop else None,
                    "destination": {"code": dst_stop.code, "name": dst_stop.name} if dst_stop else None
                },
                "validation": {
                    "source_resolved": src_stop is not None,
                    "destination_resolved": dst_stop is not None,
                    "date_valid": True
                },
                "status": "ready" if (src_stop and dst_stop) else "incomplete"
            }

        result = await service.search_routes(
            source=search_request.source,
            destination=search_request.destination,
            travel_date=travel_date_str,
            budget_category=search_request.budget,
            multi_modal=search_request.multi_modal,
            women_safety_mode=search_request.women_safety_mode,
            offset=offset,
            limit=limit
        )

        if not result or not result.get("journeys"):
            # Return smart error with suggestions (Topic 7)
            return {
                "error": "NO_ROUTES_FOUND",
                "message": f"No routes found for {search_request.source} -> {search_request.destination} on {travel_date_str}",
                "suggestions": [
                    "Try nearby stations",
                    "Try a different travel date",
                    "Check if direct trains are available on this day"
                ],
                "journeys": []
            }

        status_label = "success"
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred."
        )
    finally:
        duration = time.time() - start_time
        SEARCH_LATENCY_SECONDS.labels(endpoint="/api/search").observe(duration)
        SEARCH_REQUESTS_TOTAL.labels(endpoint="/api/search", status=status_label).inc()
        ROUTE_LATENCY_MS.observe(duration * 1000)

@router.get("/stations")
@limiter.limit("120/minute")
@cache(expire=3600) # 1 hour cache
async def autocomplete_stations(request: Request, q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    """
    Autocomplete using the GTFS Stop table.
    """
    try:
        station_service = StationService(db)
        results = station_service.search_stations_by_name(q)
        return {"stations": results}
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        return {"stations": []}

@router.get("/stations/near", response_model=List[Dict])
# @cached(ttl=3600) # Cache nearby stations for 1 hour
@limiter.limit("30/minute") # New: Rate limit to 30 requests per minute
async def get_nearby_stations_endpoint(
    request: Request, # Added Request dependency
    latitude: float = Query(..., ge=-90, le=90, description="Latitude of the current location"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude of the current location"),
    radius_km: float = Query(..., gt=0, description="Radius in kilometers to search for stations"),
    limit: int = Query(10, gt=0, le=50, description="Maximum number of nearby stations to return"),
    db: Session = Depends(get_db),
):
    """
    Finds stations near a given geographical point within a specified radius.
    """
    try:
        station_service = StationService(db)
        nearby_stations = station_service.get_stations_near_me(latitude, longitude, radius_km, limit)
        return nearby_stations
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching nearby stations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")

@router.get("/quick")
@limiter.limit("120/minute")
@cache(expire=300)
async def quick_search_endpoint(
    request: Request,
    source: str = Query(..., description="Source station code (e.g. NDLS)"),
    destination: str = Query(..., description="Destination station code (e.g. BCT)"),
    departure_time: Optional[datetime] = Query(None, description="Preferred departure time (ISO format)"),
    women_safety_mode: bool = Query(False, description="Enable women safety constraints"),
    offset: int = Query(0, ge=0),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Blueprint-compliant quick search endpoint (Topic 1).
    Now upgraded with SearchService features and Load More support.
    """
    start_time = time.time()
    try:
        search_dt = departure_time or datetime.now()
        date_str = search_dt.strftime("%Y-%m-%d")
        
        service = SearchService(db)
        result = await service.search_routes(
            source=source,
            destination=destination,
            travel_date=date_str,
            women_safety_mode=women_safety_mode,
            offset=offset,
            limit=limit
        )
        
        return {
            "source": source,
            "destination": destination,
            "departure_date": search_dt.isoformat(),
            "routes": result.get("journeys", []),
            "count": len(result.get("journeys", [])),
            "total_available": result.get("total_available", 0),
            "offset": offset,
            "limit": limit,
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    except Exception as e:
        logger.error(f"Quick search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            data = await websocket.receive_text()
            # Optionally, process received data or send pings
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
