from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging
import time
import json

from typing import Dict, List
from database import get_db
from schemas import SearchRequestSchema
from services.route_engine import route_engine
from models import StationMaster
from services.cache_service import cache_service

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
        # Query a broader set of candidates from the database
        candidates = db.query(StationMaster).filter(
            (StationMaster.station_name.ilike(f"%{query_lower}%")) |
            (StationMaster.station_code.ilike(f"{query_lower}%"))
        ).limit(50).all()

        if not candidates:
            return []

        # Rank candidates in Python
        scored_stations = [
            (calculate_station_score(station, query_lower), station) for station in candidates
        ]
        
        # Sort by score (descending), then by name (ascending)
        scored_stations.sort(key=lambda x: (-x[0], x[1].station_name))
        
        # Format the top results
        results = [{
            "name": station.station_name,
            "code": station.station_code,
            "city": station.city,
        } for score, station in scored_stations[:10]]

        if cache_service.is_available():
            cache_service.set(cache_key, results, ttl_seconds=3600) # Cache for 1 hour

        return results
    except Exception as e:
        logger.error(f"Station search autocomplete error: {e}")
        # Return empty list on error to prevent frontend from crashing
        return []
