"""
Working Search API - Minimal implementation that bypasses broken dependencies.
This provides a working search endpoint for demonstration purposes.
"""

from fastapi import APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/v3", tags=["Working Search"])

# In-memory cache for routes
_route_cache = {}


@router.get("/search/unified")
async def search_routes(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    date: str = Query(..., description="Travel date (YYYY-MM-DD)"),
    persona: str = Query("ECONOMY", description="Search persona"),
    tier: str = Query("BASIC", description="Search tier"),
    limit: int = Query(10, description="Maximum results"),
    bypass_cache: bool = Query(False, description="Force deep graph search")
):
    """
    Search for routes between two stations.
    This is a working implementation that bypasses broken dependencies.
    """
    try:
        # Generate cache key
        cache_key = f"{source.upper()}:{destination.upper()}:{date}:{persona}"
        
        # Check cache
        if cache_key in _route_cache and not bypass_cache:
            routes = _route_cache[cache_key]
            return {
                "status": "success",
                "data": {
                    "journeys": routes[:limit],
                    "grouped_journeys": {
                        "top_5_optimal": [r["journey_id"] for r in routes[:5]]
                    },
                    "pagination": {
                        "session_id": f"session-{int(time.time())}",
                        "total": len(routes)
                    }
                },
                "metadata": {
                    "engine": "working_search_v1",
                    "latency_ms": 50,
                    "cache_hit": True
                }
            }
        
        # Generate routes (simulated for demo)
        routes = generate_demo_routes(source.upper(), destination.upper(), date)
        
        # Cache the results
        _route_cache[cache_key] = routes
        
        return {
            "status": "success",
            "data": {
                "journeys": routes[:limit],
                "grouped_journeys": {
                    "top_5_optimal": [r["journey_id"] for r in routes[:5]]
                },
                "pagination": {
                    "session_id": f"session-{int(time.time())}",
                    "total": len(routes)
                }
            },
            "metadata": {
                "engine": "working_search_v1",
                "latency_ms": 150,
                "cache_hit": False
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )


def generate_demo_routes(source: str, destination: str, date: str) -> List[Dict[str, Any]]:
    """Generate demo routes for demonstration."""
    
    routes = [
        {
            "journey_id": f"route-{source}-{destination}-001",
            "train_number": "12951",
            "train_name": "Mumbai Rajdhani",
            "from_station": source,
            "to_station": destination,
            "departure_time": "16:55",
            "arrival_time": "08:35",
            "total_duration": 940,
            "total_fare": 1500,
            "availability_status": "AVAILABLE",
            "num_transfers": 0,
            "safety_score": 95,
            "legs": [
                {
                    "train_number": "12951",
                    "train_name": "Mumbai Rajdhani",
                    "from_station_code": source,
                    "to_station_code": destination,
                    "from_station_name": source,
                    "to_station_name": destination,
                    "departure_time": "16:55",
                    "arrival_time": "08:35",
                    "class_type": "3A",
                    "fare": 1500,
                    "distance": 1386,
                    "duration_minutes": 940
                }
            ]
        },
        {
            "journey_id": f"route-{source}-{destination}-002",
            "train_number": "12909",
            "train_name": "Garib Rath",
            "from_station": source,
            "to_station": destination,
            "departure_time": "18:40",
            "arrival_time": "10:25",
            "total_duration": 945,
            "total_fare": 850,
            "availability_status": "AVAILABLE",
            "num_transfers": 0,
            "safety_score": 92,
            "legs": [
                {
                    "train_number": "12909",
                    "train_name": "Garib Rath",
                    "from_station_code": source,
                    "to_station_code": destination,
                    "from_station_name": source,
                    "to_station_name": destination,
                    "departure_time": "18:40",
                    "arrival_time": "10:25",
                    "class_type": "3A",
                    "fare": 850,
                    "distance": 1386,
                    "duration_minutes": 945
                }
            ]
        },
        {
            "journey_id": f"route-{source}-{destination}-003",
            "train_number": "19019",
            "train_name": "Kota Exp",
            "from_station": source,
            "to_station": destination,
            "departure_time": "14:10",
            "arrival_time": "07:00",
            "total_duration": 1010,
            "total_fare": 650,
            "availability_status": "WAITLIST",
            "num_transfers": 0,
            "safety_score": 88,
            "legs": [
                {
                    "train_number": "19019",
                    "train_name": "Kota Exp",
                    "from_station_code": source,
                    "to_station_code": destination,
                    "from_station_name": source,
                    "to_station_name": destination,
                    "departure_time": "14:10",
                    "arrival_time": "07:00",
                    "class_type": "SL",
                    "fare": 650,
                    "distance": 1386,
                    "duration_minutes": 1010
                }
            ]
        }
    ]
    
    return routes


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "working_search"
    }


@router.get("/search/stats")
async def search_stats():
    """Get search statistics."""
    return {
        "total_searches": len(_route_cache),
        "cached_routes": sum(len(v) for v in _route_cache.values()),
        "status": "operational"
    }