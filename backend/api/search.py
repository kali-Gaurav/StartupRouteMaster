from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging
import time
import json

from typing import Dict, List
from backend.database import get_db
from backend.schemas import SearchRequestSchema
from backend.services.route_engine import route_engine
from backend.models import StationMaster, Station # Import Station model as well
from backend.services.cache_service import cache_service
from backend.services.station_service import StationService # Import StationService

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

# --- Route Search Endpoint ---

@router.post("/", response_model=Dict)
async def search_routes_endpoint(request: SearchRequestSchema):
    """
    Search for routes using the in-memory graph engine.
    This is the primary, high-performance route search endpoint.
    """
    start_time = time.time()
    try:
        routes = route_engine.search_routes(
            source=request.source,
            destination=request.destination,
            travel_date=request.date,
            budget_category=request.budget if request.budget != "all" else None,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Search for {request.source} -> {request.destination} completed in {duration_ms}ms, found {len(routes)} routes.")
        
        if not routes:
            return {"routes": [], "message": "No routes found matching your criteria."}
        
        return {"routes": routes, "message": "Search completed successfully."}
    except RuntimeError as e:
        logger.error(f"Route engine error: {e}")
        raise HTTPException(status_code=503, detail=f"The route search engine is not available: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during search: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")

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
async def search_stations_endpoint(
    q: str = Query(..., min_length=2, description="Search query for stations"),
    db: Session = Depends(get_db),
):
    """
    Provides intelligent, ranked autocomplete results for station searches.
    """
    cache_key = f"stations_autocomplete:{q.lower()}"
    if cache_service.is_available():
        cached_results = cache_service.get(cache_key)
        if cached_results:
            return cached_results

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

        if cache_service.is_available():
            cache_service.set(cache_key, results, ttl_seconds=3600) # Cache for 1 hour

        return results
    except Exception as e:
        logger.error(f"Station search autocomplete error: {e}")
        # Return empty list on error to prevent frontend from crashing
        return []

@router.get("/stations/near", response_model=List[Dict])
async def get_nearby_stations_endpoint(
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
        raise HTTPException(status_code=500, detail="Failed to fetch nearby stations.")
