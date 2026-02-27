from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db
from .db_utils import get_stop_by_id_cached
from models import Stop

app = FastAPI(title="Route Search & Optimization Service")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple request logging middleware to help trace requests coming through the API Gateway
@app.middleware("http")
async def log_requests(request, call_next):
    try:
        client_host = request.client.host if request.client else "unknown"
    except Exception:
        client_host = "unknown"

    # Don't log potentially large bodies; log headers of interest only
    interesting_headers = {k: v for k, v in request.headers.items() if k.lower() in ("user-agent", "authorization", "content-type", "x-forwarded-for")}
    logger.info(f"Incoming request {request.method} {request.url.path} from {client_host} query={dict(request.query_params)} headers={interesting_headers}")

    response = await call_next(request)
    logger.info(f"Response {response.status_code} for {request.method} {request.url.path} (from {client_host})")
    return response

class RouteRequest(BaseModel):
    source_station: str
    destination_station: str
    departure_date: str  # YYYY-MM-DD
    preferences: Optional[dict] = {}

class RouteResponse(BaseModel):
    route_id: str
    segments: List[dict]
    total_duration: int  # minutes
    total_cost: float
    feasibility_score: float
    recommendations: List[dict]

@app.post("/search", response_model=List[RouteResponse])
async def search_routes(request: RouteRequest, db: Session = Depends(get_db)):
    """Search for optimal routes between stations"""
    try:
        logger.info(f"Searching routes from {request.source_station} to {request.destination_station}")

        # --- Demonstrate caching for a stop ---
        # For demonstration, let's try to fetch a dummy stop_id (e.g., 1)
        # In a real scenario, request.source_station or destination_station
        # would be mapped to a Stop.id or Stop.stop_id to fetch details.
        dummy_stop_id_for_cache_demo = 1 # Assuming Stop.id is integer
        cached_stop = get_stop_by_id_cached(db, dummy_stop_id_for_cache_demo)
        if cached_stop:
            logger.info(f"Demo: Fetched stop (ID: {cached_stop.id}, Name: {cached_stop.name}) using cache.")
        else:
            logger.warning(f"Demo: Could not fetch stop with ID {dummy_stop_id_for_cache_demo} for cache demo (it might not exist in DB yet).")
        # --- End cache demonstration ---

        # TODO: Implement RAPTOR algorithm
        # For now, return mock response
        mock_route = RouteResponse(
            route_id=str(uuid.uuid4()),
            segments=[
                {
                    "train_number": "12345",
                    "train_name": "Express",
                    "departure_station": request.source_station,
                    "arrival_station": request.destination_station,
                    "departure_time": "10:00",
                    "arrival_time": "14:00",
                    "duration": 240,
                    "cost": 500.0
                }
            ],
            total_duration=240,
            total_cost=500.0,
            feasibility_score=0.85,
            recommendations=[]
        )

        return [mock_route]

    except Exception as e:
        logger.error(f"Error searching routes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Convenience GET endpoint so API Gateway and browsers can call /search with query params
@app.get("/search", response_model=List[RouteResponse])
async def search_routes_get(source_station: str, destination_station: str, departure_date: str, preferences: Optional[str] = None):
    prefs = {}
    if preferences:
        try:
            import json
            prefs = json.loads(preferences)
        except Exception:
            prefs = {}

    req = RouteRequest(source_station=source_station, destination_station=destination_station, departure_date=departure_date, preferences=prefs)
    return await search_routes(req)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
