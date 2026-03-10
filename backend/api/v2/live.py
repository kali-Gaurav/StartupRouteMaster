from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dependencies import get_route_engine, get_current_user
from services.multi_layer_cache import multi_layer_cache

router = APIRouter(prefix="/live", tags=["Real-time Operations"])

@router.get("/train/{train_no}")
async def get_train_tracking(
    train_no: str = Path(..., min_length=1),
    engine=Depends(get_route_engine)
):
    """
    Get real-time train location and delay.
    Includes 'Predicted ETA' logic based on current delays (Upgrade Suggestion).
    """
    await multi_layer_cache.initialize()
    # Check cache first (Suggestion #2)
    cache_key = f"live:train:{train_no}"
    cached = await multi_layer_cache.redis.get(cache_key)
    if cached:
        import json
        return json.loads(cached)

    # In real life, we fetch from external API here. 
    # For now, we use the graph overlay to see if we have ingested data.
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
    
    # Cache for 1 minute
    if multi_layer_cache.redis:
        import json
        await multi_layer_cache.redis.set(cache_key, json.dumps(res), ex=60)
        
    return res

@router.get("/dead-zone")
async def check_dead_zone(lat: float, lng: float, speed: float = 60.0):
    """
    Predicts upcoming dead zones and returns an emergency directory for offline use.
    """
    from services.emergency.safety_service import safety_service
    return await safety_service.predict_dead_zone(lat, lng, speed)

@router.get("/station/{station_code}")
async def get_station_board(
    station_code: str,
    engine=Depends(get_route_engine)
):
    """
    Live departure board for a station.
    Filters the O(1) time index for the next 4 hours.
    """
    station_code = station_code.upper()
    snapshot = engine.current_snapshot
    
    # Task 4.1: O(1) Station Code to ID resolution
    sid = None
    if hasattr(snapshot, 'station_code_to_id'):
        sid = snapshot.station_code_to_id.get(station_code)
    else:
        # Fallback for older snapshots (temporary)
        for stop_id, stop in snapshot.stop_cache.items():
            if getattr(stop, 'code', '') == station_code:
                sid = stop_id
                break
    
    if not sid:
        raise HTTPException(status_code=404, detail="Station not found")

    if not engine.current_graph:
        raise HTTPException(status_code=503, detail="Route engine is warming up")

    # Get departures for next 240 minutes (4 hours)
    now = datetime.now()
    departures = engine.current_graph.get_departures_from_stop(sid, now, lookahead_minutes=240)
    
    board = []
    overlay = engine.current_graph.overlay
    for dep_time, trip_id in departures:
        path = snapshot.train_path.get(trip_id, [])
        dest = path[-1] if path else {}
        
        # Task 4.2: Integrated Delay Logic
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
        
    return {
        "station": station_code,
        "departures": board,
        "count": len(board)
    }
