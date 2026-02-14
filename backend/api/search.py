from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import logging
import time
import json

from typing import Dict, List, Optional
from backend.database import get_db
from backend.schemas import SearchRequestSchema
from backend.services.route_engine import route_engine
from backend.models import StationMaster, Station # Import Station model as well
from backend.services.cache_service import cache_service
from backend.services.station_service import StationService # Import StationService
from backend.services.hybrid_search_service import HybridSearchService # Import HybridSearchService
from backend.config import Config # Import Config
from fastapi_cache.decorator import cached # Import cached decorator
from backend.api.websockets import manager as websocket_manager # Import the shared WebSocket manager
from backend.app import limiter # Import the shared limiter
from backend.utils.metrics import SEARCH_LATENCY_SECONDS, SEARCH_REQUESTS_TOTAL # Import custom metrics

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

# --- Route Search Endpoint ---

@router.post("/", response_model=Dict)
@cached(ttl=60) # Cache search results for 60 seconds
@limiter.limit("5/minute") # Rate limit to 5 requests per minute
async def search_routes_endpoint(request: Request, search_request: SearchRequestSchema, db: Session = Depends(get_db), websocket: Optional[WebSocket] = None): # Added websocket parameter
    """
    Search for routes using the hybrid search engine (external API with internal graph fallback).
    If a WebSocket is provided, results will be streamed.
    """
    if websocket:
        await websocket_manager.connect(websocket)
        await websocket.send_json({"status": "searching", "message": "Starting route search..."})

    start_time = time.time()
    status_label = "failure" # Default to failure

    try:
        hybrid_search_service = HybridSearchService(db, route_engine)
        routes = await hybrid_search_service.search_routes(
            source=search_request.source,
            destination=search_request.destination,
            travel_date=search_request.date,
            budget_category=search_request.budget if search_request.budget != "all" else None,
            multi_modal=search_request.multi_modal,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Hybrid search for {search_request.source} -> {search_request.destination} completed in {duration_ms}ms, found {len(routes)} routes.")
        
        response_data = {"routes": routes, "message": "Search completed successfully."}
        status_label = "success" # Set to success if no exception

        if websocket:
            await websocket.send_json({"status": "completed", "results": response_data})
            return # WebSocket handles response
        
        return response_data # For HTTP requests
    except RuntimeError as e:
        logger.error(f"Route engine error: {e}")
        if websocket:
            await websocket.send_json({"status": "error", "message": f"The route search engine is not available: {e}"})
            return
        raise HTTPException(status_code=503, detail=f"The route search engine is not available: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during search: {e}")
        if websocket:
            await websocket.send_json({"status": "error", "message": "An unexpected error occurred during search."})
            return
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")
    finally:
        # Observe search latency and increment total requests
        SEARCH_LATENCY_SECONDS.labels(endpoint="/api/search").observe(time.time() - start_time)
        SEARCH_REQUESTS_TOTAL.labels(endpoint="/api/search", status=status_label).inc()


# --- Station Autocomplete Endpoint ---

def calculate_station_score(station: StationMaster, query: str) -> int:
    """Calculates a relevance score for a station based on the query."""
    query_lower = query.lower()
    name_lower = station.station_name.lower()
    code_lower = station.station_code.lower()
    
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
    
    if station.is_junction:
        score += 100
        
    return score

@router.get("/stations", response_model=List[Dict])
@cached(ttl=3600) # Cache station autocomplete results for 1 hour
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
@cached(ttl=3600) # Cache nearby stations for 1 hour
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
