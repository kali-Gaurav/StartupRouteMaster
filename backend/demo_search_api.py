"""
Simple Demo Search API for Teacher Demonstration.
Provides route search functionality without complex dependencies.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any

app = FastAPI(title="RouteMaster Demo API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock route data for demonstration
MOCK_ROUTES = [
    {
        "journey_id": "route-001",
        "train_number": "12951",
        "train_name": "Mumbai Rajdhani",
        "from_station": "NDLS",
        "to_station": "MMCT",
        "departure_time": "16:55",
        "arrival_time": "08:35",
        "total_duration": 940,
        "total_fare": 1500,
        "availability_status": "AVAILABLE",
        "num_transfers": 0,
        "safety_score": 95,
        "segments": [
            {
                "train_number": "12951",
                "train_name": "Mumbai Rajdhani",
                "from_station_code": "NDLS",
                "to_station_code": "MMCT",
                "from_station_name": "New Delhi",
                "to_station_name": "Mumbai Central",
                "departure_time": "16:55",
                "arrival_time": "08:35",
                "class_type": "3A",
                "fare": 1500,
                "distance": 1386
            }
        ]
    },
    {
        "journey_id": "route-002",
        "train_number": "12909",
        "train_name": "Garib Rath",
        "from_station": "NDLS",
        "to_station": "MMCT",
        "departure_time": "18:40",
        "arrival_time": "10:25",
        "total_duration": 945,
        "total_fare": 850,
        "availability_status": "AVAILABLE",
        "num_transfers": 0,
        "safety_score": 92,
        "segments": [
            {
                "train_number": "12909",
                "train_name": "Garib Rath",
                "from_station_code": "NDLS",
                "to_station_code": "MMCT",
                "from_station_name": "New Delhi",
                "to_station_name": "Mumbai Central",
                "departure_time": "18:40",
                "arrival_time": "10:25",
                "class_type": "3A",
                "fare": 850,
                "distance": 1386
            }
        ]
    },
    {
        "journey_id": "route-003",
        "train_number": "19019",
        "train_name": "Kota Exp",
        "from_station": "NDLS",
        "to_station": "MMCT",
        "departure_time": "14:10",
        "arrival_time": "07:00",
        "total_duration": 1010,
        "total_fare": 650,
        "availability_status": "WAITLIST",
        "num_transfers": 0,
        "safety_score": 88,
        "segments": [
            {
                "train_number": "19019",
                "train_name": "Kota Exp",
                "from_station_code": "NDLS",
                "to_station_code": "MMCT",
                "from_station_name": "New Delhi",
                "to_station_name": "Mumbai Central",
                "departure_time": "14:10",
                "arrival_time": "07:00",
                "class_type": "SL",
                "fare": 650,
                "distance": 1386
            }
        ]
    }
]


@app.get("/api/v3/search/unified")
async def search_routes(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    date: str = Query(..., description="Travel date (YYYY-MM-DD)"),
    persona: str = Query("ECONOMY", description="Search persona"),
    tier: str = Query("BASIC", description="Search tier"),
    limit: int = Query(10, description="Maximum results")
):
    """
    Search for routes between two stations.
    """
    # Simulate search delay
    await asyncio.sleep(0.5)
    
    # Filter routes based on source/destination (case insensitive)
    source_upper = source.upper()
    dest_upper = destination.upper()
    
    routes = [r for r in MOCK_ROUTES if r["from_station"] == source_upper and r["to_station"] == dest_upper]
    
    # If no exact match, return all routes as demo
    if not routes:
        routes = MOCK_ROUTES
    
    return {
        "status": "success",
        "data": {
            "journeys": routes[:limit],
            "grouped_journeys": {
                "top_5_optimal": [r["journey_id"] for r in routes[:5]]
            },
            "pagination": {
                "session_id": f"demo-{int(time.time())}",
                "total": len(routes)
            }
        },
        "metadata": {
            "engine": "demo_engine",
            "latency_ms": 500,
            "cache_hit": False
        }
    }


@app.get("/api/v3/search/stream")
async def stream_routes(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    date: str = Query(..., description="Travel date (YYYY-MM-DD)")
):
    """
    Stream routes progressively using SSE.
    """
    async def event_generator():
        source_upper = source.upper()
        dest_upper = destination.upper()
        
        routes = [r for r in MOCK_ROUTES if r["from_station"] == source_upper and r["to_station"] == dest_upper]
        if not routes:
            routes = MOCK_ROUTES
        
        for i, route in enumerate(routes):
            chunk = {
                "chunk": "ENRICHED",
                "journeys": [route],
                "latency_ms": (i + 1) * 100,
                "status": "streaming"
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.3)
        
        # End signal
        yield f"data: {json.dumps({'chunk': 'end', 'status': 'complete'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)