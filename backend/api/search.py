from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import logging
import time
import json
from datetime import datetime, date
from typing import Dict, List, Optional

from backend.database import get_db
from backend.schemas import SearchRequestSchema
from backend.services.multi_modal_route_engine import multi_modal_route_engine
from backend.models import StationMaster, Station, Disruption
from backend.services.cache_service import cache_service
from backend.services.station_service import StationService
from backend.services.hybrid_search_service import HybridSearchService
from backend.config import Config
from backend.api.websockets import manager as websocket_manager
from backend.utils.limiter import limiter
from backend.utils.metrics import SEARCH_LATENCY_SECONDS, SEARCH_REQUESTS_TOTAL

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)

# --- Route Search Endpoint ---

@router.post("/", response_model=None)
@limiter.limit("5/minute")
async def search_routes_endpoint(request: Request, search_request: SearchRequestSchema, db: Session = Depends(get_db)):
    """
    Search for multi-modal routes using the GTFS-based MultiModalRouteEngine.
    Supports single journeys, connecting journeys, circular trips, and multi-city booking.
    """
    start_time = time.time()
    status_label = "failure"

    try:
        # Ensure the multi-modal engine is loaded
        if not multi_modal_route_engine._is_loaded:
            multi_modal_route_engine.load_graph_from_db(db)

        # Parse travel date
        travel_date = datetime.fromisoformat(search_request.date).date()

        # Find source and destination stop IDs
        source_stop_id = None
        dest_stop_id = None

        # Search by station name (simplified - in production, use proper geocoding)
        for stop_id, stop_info in multi_modal_route_engine.stops_map.items():
            if stop_info['name'].lower() == search_request.source.lower():
                source_stop_id = stop_id
            if stop_info['name'].lower() == search_request.destination.lower():
                dest_stop_id = stop_id

        if not source_stop_id or not dest_stop_id:
            raise HTTPException(status_code=404, detail="Source or destination station not found")

        # Search for journeys based on request type
        if hasattr(search_request, 'journey_type') and search_request.journey_type == 'connecting':
            # First get individual journeys
            individual_journeys = multi_modal_route_engine.search_single_journey(
                source_stop_id, dest_stop_id, travel_date
            )
            routes = multi_modal_route_engine.search_connecting_journeys(individual_journeys)
        elif hasattr(search_request, 'journey_type') and search_request.journey_type == 'circular':
            # For circular, we need return date
            if hasattr(search_request, 'return_date'):
                return_date = datetime.fromisoformat(search_request.return_date).date()
                outward_journeys = multi_modal_route_engine.search_single_journey(
                    source_stop_id, dest_stop_id, travel_date
                )
                if outward_journeys:
                    routes = multi_modal_route_engine.search_circular_journey(
                        outward_journeys[0], return_date
                    )
                else:
                    routes = []
            else:
                routes = []
        elif hasattr(search_request, 'cities') and search_request.cities:
            # Multi-city booking
            routes = multi_modal_route_engine.search_multi_city_journey(
                search_request.cities, [travel_date] * len(search_request.cities)
            )
        else:
            # Single journey
            routes = multi_modal_route_engine.search_single_journey(
                source_stop_id, dest_stop_id, travel_date
            )

        # Apply fare calculation with concessions
        passenger_type = getattr(search_request, 'passenger_type', 'adult')
        concessions = getattr(search_request, 'concessions', [])

        for route in routes:
            fare_info = multi_modal_route_engine.calculate_fare_with_concessions(
                route, passenger_type, concessions
            )
            route['fare_details'] = fare_info

        # Simulate real-time delays
        for route in routes:
            route_with_delays = multi_modal_route_engine.simulate_real_time_delays(route, db)
            route.update(route_with_delays)

        # Check for disruptions
        disruptions = db.query(Disruption).filter(
            Disruption.status == "active"
        ).all()

        disruption_alerts = []
        for d in disruptions:
            disruption_alerts.append({
                "type": d.disruption_type,
                "description": d.description,
                "severity": d.severity or "medium",
                "affected_routes": d.gtfs_route_id
            })

        response_data = {
            "routes": routes,
            "disruption_alerts": disruption_alerts,
            "message": f"Found {len(routes)} multi-modal journey options."
        }
        status_label = "success"

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Multi-modal search completed in {duration_ms}ms, found {len(routes)} routes.")

        return response_data

    except RuntimeError as e:
        logger.error(f"Route engine error: {e}")
        raise HTTPException(status_code=503, detail=f"The multi-modal route search engine is not available: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during search: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search.")
    finally:
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
