from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from datetime import datetime
from database.session import get_transit_db
from dependencies import get_route_engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from utils.responses import success_response, v3_response
import logging

logger = logging.getLogger("api.debug")
router = APIRouter(prefix="/debug", tags=["Deep Verification"])

@router.get("/graph/status")
async def get_graph_status(engine=Depends(get_route_engine)):
    """Inspect the current memory-resident graph snapshot."""
    snapshot = engine.current_snapshot
    if not snapshot:
        return success_response(data={"status": "No snapshot loaded"})
    
    data = {
        "date": snapshot.date,
        "total_stops": len(snapshot.stop_cache),
        "total_trip_segments": len(snapshot.trip_segments),
        "total_route_patterns": len(snapshot.route_patterns),
        "has_time_index": len(snapshot.station_time_index) > 0,
        "has_reliability_scores": len(snapshot.reliability_scores) > 0
    }
    return success_response(data=data)

@router.get("/station/{station_id}/index")
async def inspect_station_index(station_id: int, engine=Depends(get_route_engine)):
    """Deep-dive into the O(1) hour-bucket index for a specific station."""
    snapshot = engine.current_snapshot
    if not snapshot: raise HTTPException(status_code=400, detail="Snapshot not loaded")
    
    buckets = snapshot.station_time_index.get(station_id)
    if not buckets:
        return success_response(message=f"Station {station_id} has no departures indexed.", data={})
    
    analysis = {}
    for h in range(24):
        analysis[f"hour_{h}"] = {
            "count": len(buckets[h]),
            "trips": [tid for _, tid in buckets[h]]
        }
    return success_response(data=analysis)

@router.get("/trip/{trip_id}/path")
async def get_trip_path(trip_id: int, engine=Depends(get_route_engine)):
    """Verify the exact station sequence and timing for a specific trip."""
    path = engine.current_snapshot.train_path.get(trip_id)
    if not path:
        raise HTTPException(status_code=404, detail="Trip not found in snapshot")
    return success_response(data=path)

@router.get("/transit-index/{station_code}")
async def get_raw_transit_index(station_code: str, db: Session = Depends(get_transit_db)):
    """Inspect the raw station_transit_index JSON stored in SQLite."""
    res = db.execute(
        text("SELECT trains_map FROM station_transit_index WHERE station_code = :code"),
        {"code": station_code.upper()}
    ).fetchone()
    
    if not res:
        raise HTTPException(status_code=404, detail="Station code not found in index")
    
    import json
    return success_response(data=json.loads(res[0]))

@router.get("/reliability/{trip_id}/{station_id}")
async def get_point_reliability(trip_id: int, station_id: int, engine=Depends(get_route_engine)):
    """Check the real-time reliability score for a trip at a station."""
    scores = engine.current_snapshot.reliability_scores
    score = scores.get((trip_id, station_id), 1.0)
    data = {
        "trip_id": trip_id,
        "station_id": station_id,
        "reliability_score": score,
        "is_default": (trip_id, station_id) not in scores
    }
    return success_response(data=data)
