from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dependencies import get_route_engine, get_current_user
from services.multi_layer_cache import multi_layer_cache
from utils.responses import success_response, v3_response
import logging
import json

logger = logging.getLogger("api.live")
router = APIRouter(prefix="/live", tags=["Real-time Operations"])

@router.get("/train/{train_no}")
async def get_train_tracking(
    train_no: str = Path(..., min_length=1),
    engine=Depends(get_route_engine)
):
    """Get real-time train location and delay."""
    await multi_layer_cache.initialize()
    cache_key = f"live:train:{train_no}"
    cached = await multi_layer_cache.redis.get(cache_key)
    if cached:
        return success_response(data=json.loads(cached))

    snapshot = engine.current_snapshot
    trip_id = None
    if snapshot:
        for tid, segments in snapshot.trip_segments.items():
            if segments and segments[0].train_number == train_no:
                trip_id = tid
                break
    
    delay = engine.current_graph.overlay.get_trip_delay(trip_id) if trip_id else 0
    
    res = {
        "train_no": train_no,
        "status": "Running" if delay < 60 else "Delayed",
        "delay_minutes": delay,
        "last_updated": datetime.utcnow().isoformat(),
        "source": "Railway Graph Overlay"
    }
    
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.set(cache_key, json.dumps(res), ex=60)
        
    logger.info(f"LIVE_TRAIN_TRACKING | {train_no} | delay={delay}")
    return success_response(data=res)

@router.get("/dead-zone")
async def check_dead_zone(lat: float, lng: float, speed: float = 60.0):
    """Predicts upcoming dead zones and returns an emergency directory for offline use."""
    from services.emergency.safety_service import safety_service
    data = await safety_service.predict_dead_zone(lat, lng, speed)
    return success_response(data=data)

@router.get("/station/{station_code}")
async def get_station_board(
    station_code: str,
    engine=Depends(get_route_engine)
):
    """Live departure board for a station."""
    station_code = station_code.upper()
    snapshot = engine.current_snapshot
    
    sid = None
    station_code_to_id = getattr(snapshot, "station_code_to_id", None)
    if station_code_to_id is not None:
        sid = station_code_to_id.get(station_code)
    else:
        for stop_id, stop in getattr(snapshot, "stop_cache", {}).items():
            if getattr(stop, 'code', '') == station_code:
                sid = stop_id
                break
    
    if not sid:
        raise HTTPException(status_code=404, detail="Station not found")

    if not engine.current_graph:
        raise HTTPException(status_code=503, detail="Route engine is warming up")

    now = datetime.now()
    departures = engine.current_graph.get_departures_from_stop(sid, now, lookahead_minutes=240)
    
    board = []
    overlay = engine.current_graph.overlay
    for dep_time, trip_id in departures:
        path = snapshot.train_path.get(trip_id, [])
        dest = path[-1] if path else {}
        
        real_delay = overlay.get_trip_delay(trip_id) if overlay else 0
        actual_dep = dep_time + timedelta(minutes=real_delay)
        
        board.append({
            "scheduled_time": dep_time.strftime("%H:%M"),
            "actual_time": actual_dep.strftime("%H:%M"),
            "delay": real_delay,
            "train_no": snapshot.trip_segments.get(trip_id, [type('obj', (object,), {'train_number': '??'})])[0].train_number,
            "destination": snapshot.stop_cache.get(dest.get('station_id', 0), type('obj', (object,), {'name': 'Unknown'})).name,
            "status": "Delayed" if real_delay > 15 else "On Time"
        })
        
    logger.info(f"LIVE_STATION_BOARD | {station_code} | count={len(board)}")
    return success_response(data={
        "station": station_code,
        "departures": board,
        "count": len(board)
    })
