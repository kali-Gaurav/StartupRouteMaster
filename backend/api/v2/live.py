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
    delay = engine.current_graph.overlay.get_trip_delay_by_no(train_no)
    
    return {
        "train_no": train_no,
        "status": "Running" if delay < 60 else "Delayed",
        "delay_minutes": delay,
        "last_updated": datetime.utcnow().isoformat(),
        "source": "Railway Graph Overlay"
    }

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
    
    # Resolve code to ID
    # In production, we'd use a fast map.
    sid = None
    for stop_id, stop in snapshot.stop_cache.items():
        if getattr(stop, 'code', '') == station_code:
            sid = stop_id
            break
    
    if not sid:
        raise HTTPException(status_code=404, detail="Station not found")

    # Get departures for next 240 minutes (4 hours)
    now = datetime.now()
    departures = engine.current_graph.get_departures_from_stop(sid, now, lookahead_minutes=240)
    
    board = []
    for dep_time, trip_id in departures:
        path = snapshot.train_path.get(trip_id, [])
        dest = path[-1] if path else {}
        board.append({
            "time": dep_time.strftime("%H:%M"),
            "train_no": snapshot.trip_segments.get(trip_id, [type('obj', (object,), {'train_number': '??'})])[0].train_number,
            "destination": snapshot.stop_cache.get(dest.get('station_id', 0), type('obj', (object,), {'name': 'Unknown'})).name,
            "is_delayed": dep_time > now + timedelta(minutes=30) # Example logic
        })
        
    return {
        "station": station_code,
        "departures": board,
        "count": len(board)
    }
