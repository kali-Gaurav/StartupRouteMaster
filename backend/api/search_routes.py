"""
Search API Routes - REST endpoints for route search.
"""

import logging
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from services.route_engine import get_route_engine, Journey

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    """Search request schema."""
    source: str = Field(..., min_length=2, max_length=10, description="Origin station code")
    destination: str = Field(..., min_length=2, max_length=10, description="Destination station code")
    travel_date: str = Field(..., description="Travel date (YYYY-MM-DD)")
    class_type: Optional[str] = Field(None, description="Preferred class type")
    max_transfers: int = Field(3, ge=0, le=5, description="Maximum transfers")
    persona: str = Field("comfort", description="Ranking persona: comfort, budget, fast")


class SearchResponse(BaseModel):
    """Search response schema."""
    search_id: str
    journeys: List[dict]
    total_results: int
    search_time_ms: int
    expires_at: str
    demand_factor: float


@router.post("/", response_model=SearchResponse)
async def search_routes(request: SearchRequest):
    """
    Search for travel routes between stations.
    
    This endpoint uses multi-algorithm route discovery:
    - Direct routes (TurboRouter)
    - 1-transfer routes (Hub Intersection)
    - Multi-transfer routes (RAPTOR)
    
    Results are ranked by persona preference.
    """
    import uuid
    import time
    
    start_time = time.time()
    
    try:
        # Parse travel date
        travel_date = datetime.strptime(request.travel_date, "%Y-%m-%d").date()
        
        # Execute search
        route_engine = get_route_engine()
        journeys = await route_engine.search_routes(
            source_code=request.source.upper(),
            dest_code=request.destination.upper(),
            travel_date=travel_date,
            max_transfers=request.max_transfers,
            class_type=request.class_type,
            persona=request.persona
        )
        
        # Format journeys for response
        journey_dicts = []
        for journey in journeys:
            journey_dicts.append({
                "journey_id": journey.journey_id,
                "train_numbers": [s.train_number for s in journey.segments],
                "from_station": journey.segments[0].from_station_code,
                "to_station": journey.segments[-1].to_station_code,
                "departure_time": str(journey.departure_time),
                "arrival_time": str(journey.arrival_time),
                "duration_minutes": journey.total_duration,
                "transfers": journey.transfers,
                "total_fare": journey.total_fare,
                "demand_factor": journey.demand_factor,
                "safety_score": journey.safety_score,
                "availability_status": journey.availability_status,
                "segments": [
                    {
                        "train_number": s.train_number,
                        "train_name": s.train_name,
                        "from_station": s.from_station_code,
                        "to_station": s.to_station_code,
                        "departure_time": str(s.departure_time),
                        "arrival_time": str(s.arrival_time),
                        "duration_minutes": s.duration_minutes,
                        "class_type": s.class_type,
                        "fare": s.fare,
                        "availability": s.availability
                    }
                    for s in journey.segments
                ]
            })
        
        search_time = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            search_id=str(uuid.uuid4()),
            journeys=journey_dicts,
            total_results=len(journey_dicts),
            search_time_ms=search_time,
            expires_at=(datetime.now().isoformat()),
            demand_factor=journeys[0].demand_factor if journeys else 1.0
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get("/stations")
async def search_stations(q: str = Query(..., min_length=2, description="Search query")):
    """
    Search for stations by name or code.
    
    Returns matching stations for autocomplete.
    """
    # In production, query station database
    stations = [
        {"code": "NDLS", "name": "New Delhi", "city": "Delhi"},
        {"code": "BCT", "name": "Mumbai Central", "city": "Mumbai"},
        {"code": "MAS", "name": "Chennai Central", "city": "Chennai"},
        {"code": "HWH", "name": "Howrah Junction", "city": "Kolkata"},
        {"code": "SC", "name": "Secunderabad", "city": "Hyderabad"},
        {"code": "LKO", "name": "Lucknow", "city": "Lucknow"},
        {"code": "JP", "name": "Jaipur", "city": "Jaipur"},
        {"code": "PNBE", "name": "Patna", "city": "Patna"},
    ]
    
    # Filter by query
    q_lower = q.lower()
    matching = [
        s for s in stations
        if q_lower in s["code"].lower() or q_lower in s["name"].lower() or q_lower in s["city"].lower()
    ]
    
    return {"stations": matching[:10]}


@router.get("/trains/{train_number}/schedule")
async def get_train_schedule(
    train_number: str,
    date: str = Query(..., description="Travel date (YYYY-MM-DD)")
):
    """
    Get schedule for a specific train on a date.
    """
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # In production, query actual schedule
        schedule = {
            "train_number": train_number,
            "train_name": "Express",
            "date": date,
            "stops": [
                {
                    "station_code": "NDLS",
                    "station_name": "New Delhi",
                    "arrival": None,
                    "departure": "06:00",
                    "day": 0
                },
                {
                    "station_code": "BCT",
                    "station_name": "Mumbai Central",
                    "arrival": "22:00",
                    "departure": None,
                    "day": 0
                }
            ]
        }
        
        return schedule
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get train schedule"
        )