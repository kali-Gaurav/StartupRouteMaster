from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
import logging
import time
import json
from datetime import datetime, date
from typing import Dict, List, Optional

from backend.database import get_db
from backend.schemas import SearchRequestSchema
from backend.core.route_engine import route_engine
from backend.database.models import StationMaster, Station, Disruption
from backend.services.cache_service import cache_service
from backend.services.station_service import StationService
from backend.services.search_service import SearchService
from backend.database.config import Config
from backend.api.websockets import manager as websocket_manager
from backend.utils.limiter import limiter
from backend.utils.metrics import SEARCH_LATENCY_SECONDS, SEARCH_REQUESTS_TOTAL, ROUTE_LATENCY_MS
from backend.utils.station_utils import resolve_stations, find_stations_by_partial_name  # NEW
from backend.utils.validation import SearchRequestValidator, validate_date_string  # NEW

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

# --- Route Search Endpoint ---

@router.post("/", response_model=None)
@limiter.limit("5/minute")
async def search_routes_endpoint(request: Request, search_request: SearchRequestSchema, db: Session = Depends(get_db)):
    """
    Search for multi-modal routes using the consolidated SearchService.
    Ensures consistency between legacy and integrated search responses.
    """
    start_time = time.time()
    SEARCH_REQUESTS_TOTAL.inc()
    request_id = f"{datetime.utcnow().timestamp()}"
    status_label = "failure"

    try:
        # Validate travel date string
        travel_date_str = search_request.date or datetime.now().strftime("%Y-%m-%d")
        if not validate_date_string(travel_date_str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Invalid travel date format. Use YYYY-MM-DD."}
            )

        # Use unified SearchService
        service = SearchService(db)
        result = await service.search_routes(
            source=search_request.source,
            destination=search_request.destination,
            travel_date=travel_date_str
        )

        if not result or not result.get("routes"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No routes found for {search_request.source} -> {search_request.destination} on {travel_date_str}"
            )

        status_label = "success"
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search endpoint error for request {request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred during search."
        )
    finally:
        duration = time.time() - start_time
        SEARCH_LATENCY_SECONDS.labels(endpoint="/api/search").observe(duration)
        SEARCH_REQUESTS_TOTAL.labels(endpoint="/api/search", status=status_label).inc()

# --- Station Autocomplete Endpoint (Rate Limited) ---
        ROUTE_LATENCY_MS.observe(duration * 1000)


# --- Station Autocomplete Endpoint (Rate Limited) ---

def calculate_station_score(station, query_lower):
    """
    Calculate a relevance score for a station based on the search query.
    """
    name_lower = station.name.lower()
    code_lower = station.id.lower()
    
    score = 0
    if query_lower == code_lower:
        score += 1000
    elif query_lower == name_lower:
        score += 800
    elif name_lower.startswith(query_lower):
        score += 500
    elif code_lower.startswith(query_lower):
        score += 400
    elif query_lower in name_lower:
        score += 200
    
    if getattr(station, 'is_junction', False):
        score += 100
        
    return score


@router.get("/stations/autocomplete")
@limiter.limit("10/minute")  # NEW: Rate limiting to prevent enumeration
def autocomplete_stations(request: Request, query: str = Query(..., min_length=2, max_length=100), 
                         db: Session = Depends(get_db)):
    """
    Autocomplete stations based on partial name.
    NEW: Rate limited to prevent abuse. Accepts `request` so slowapi can access limiter context.
    """
    try:
        stations = find_stations_by_partial_name(db, query, limit=10)
        
        results = [
            {
                "id": station.stop_id,
                "name": station.name,
                "city": station.city,
                "code": station.code
            }
            for station in stations
        ]
        
        logger.debug(f"Autocomplete for '{query}': {len(results)} results")
        return {"results": results}
    
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                          detail="Failed to autocomplete stations")

@router.get("/stations", response_model=List[Dict])
# @cached(ttl=3600) # Cache station autocomplete results for 1 hour
@limiter.limit("30/minute") # New: Rate limit to 30 requests per minute
async def search_stations_endpoint(
    request: Request, # Added Request dependency
    q: str = Query(..., min_length=2, description="Search query for stations"),
    db: Session = Depends(get_db),
):
    """
    Provides intelligent, ranked autocomplete results for station searches.
    """
    # The cache_service.get and cache_service.set logic is now handled by @cached decorator
    # Remove manual caching logic
    # cache_key = f"stations_autocomplete:{q.lower()}"
    # if cache_service.is_available():
    #     cached_results = cache_service.get(cache_key)
    #     if cached_results:
    #         return cached_results

    try:
        query_lower = q.lower()
        # Use Station model for querying, as it now has geom column
        candidates = db.query(Station).filter(
            (Station.name.ilike(f"%{query_lower}%")) |
            (Station.id.ilike(f"{query_lower}%")) # Assuming station ID can be used as code
        ).limit(50).all()

        if not candidates:
            return []

        # Rank candidates in Python
        scored_stations = [
            (calculate_station_score(station, query_lower), station) for station in candidates
        ]
        
        # Sort by score (descending), then by name (ascending)
        scored_stations.sort(key=lambda x: (-x[0], x[1].name)) # Use station.name now
        
        # Format the top results
        results = [{
            "name": station.name,
            "code": station.id, # Use station.id as code
            "city": station.city,
        } for score, station in scored_stations[:10]]

        # The cache_service.set logic is now handled by @cached decorator
        # if cache_service.is_available():
        #     cache_service.set(cache_key, results, ttl_seconds=3600) # Cache for 1 hour

        return results
    except Exception as e:
        logger.error(f"Station search autocomplete error: {e}")
        # Return empty list on error to prevent frontend from crashing
        return []

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
