from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from datetime import datetime
from api.safety.sos import _load_event, _save_event
from api.websockets import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/safety", tags=["Safety Resilience"])

class BatteryStatusPayload(BaseModel):
    battery_level: float # 0.0 to 1.0
    is_charging: bool
    last_known_lat: float
    last_known_lng: float

@router.post("/{event_id}/battery-status")
async def update_battery_status(event_id: str, payload: BatteryStatusPayload):
    """
    Task 47: Handles battery-critical mode logic.
    """
    event = _load_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Incident not found.")
        
    # Update event state
    event["battery_level"] = payload.battery_level
    event["is_charging"] = payload.is_charging
    
    # Subtask 47.1: "Last Breath" Logic (< 3% battery)
    if payload.battery_level < 0.03 and not payload.is_charging:
        logger.error(f"🪫 [BATTERY CRITICAL] User {event.get('name')} battery at {payload.battery_level*100}%. Triggering Last Breath sync.")
        event["extra"] = f"{event.get('extra', '')} | ⚠️ DEVICE DISCONNECTING: BATTERY < 3%"
        event["priority"] = "critical"
        
        # Log final high-accuracy GPS
        if "location_history" not in event: event["location_history"] = []
        event["location_history"].append({
            "lat": payload.last_known_lat,
            "lng": payload.last_known_lng,
            "ts": datetime.utcnow().isoformat(),
            "note": "LAST_BREATH_SYNC"
        })
        
        # Subtask 47.2: Text-Only Fallback
        event["ui_mode_hint"] = "TEXT_ONLY_LOW_POWER"
        
    elif payload.battery_level < 0.15:
        # Throttle GPS Frequency hint
        event["ui_mode_hint"] = "THROTTLE_GPS_5MIN"
        logger.warning(f"🔋 [BATTERY LOW] User {event.get('name')} battery at {payload.battery_level*100}%.")

    _save_event(event)
    await manager.broadcast_sos(event)
    
    return {
        "status": "received", 
        "hint": event.get("ui_mode_hint", "NORMAL"),
        "last_breath_triggered": payload.battery_level < 0.03
    }
