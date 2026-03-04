from fastapi import APIRouter, HTTPException, Request, Body, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import json
import os
import httpx

# create logger for this module
logger = logging.getLogger(__name__)

from database.models import User
from api.dependencies import get_optional_user
from services.cache_service import cache_service
from api.websockets import manager
from services.emergency.alert_manager import EmergencyAlertManager
from utils.limiter import limiter

router = APIRouter(tags=["sos"])

_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_events: List[Dict[str, Any]] = []
SOS_KEY_PREFIX = "sos:event:"
SOS_INDEX_KEY = "sos:events"
EMERGENCY_FILE_CACHE = "emergency_cache.json"

def _save_to_file():
    try:
        with open(EMERGENCY_FILE_CACHE, 'w') as f:
            json.dump(_local_events, f)
    except Exception as e:
        logger.error(f"Failed to save emergency cache to file: {e}")

def _load_from_file():
    global _local_events
    if os.path.exists(EMERGENCY_FILE_CACHE):
        try:
            with open(EMERGENCY_FILE_CACHE, 'r') as f:
                _local_events = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load emergency cache from file: {e}")

# Initial load
_load_from_file()

# --- Models ---
class SOSTrip(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    mode: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    boarding_time: Optional[str] = None
    eta: Optional[str] = None

class SOSPayload(BaseModel):
    lat: float
    lng: float
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    extra: Optional[str] = None
    trip: Optional[SOSTrip] = None
    chat_history: Optional[List[Dict[str, str]]] = None

class SOSEventResponse(BaseModel):
    id: str
    lat: float
    lng: float
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    extra: Optional[str] = None
    trip: Optional[SOSTrip] = None
    status: str
    priority: str
    category: Optional[str] = None
    triggered_at: str
    google_maps_url: str
    resolved_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    escalation_level: Optional[int] = 1
    call_logs: Optional[List[Dict[str, str]]] = []
    structured_info: Optional[Dict[str, Any]] = {}
    active_participants: Optional[List[str]] = []
    location_history: Optional[List[Dict[str, Any]]] = []

# --- Internal Helpers ---
def _event_key(event_id: str) -> str:
    return f"{SOS_KEY_PREFIX}{event_id}"

def _save_event(event: Dict[str, Any]):
    from utils.encryption import encrypt_sos_event
    storage_event = encrypt_sos_event(event)
    if _redis:
        try:
            _redis.set(_event_key(storage_event['id']), json.dumps(storage_event))
            _redis.sadd(SOS_INDEX_KEY, storage_event['id'])
        except Exception: pass
    global _local_events
    for i, e in enumerate(_local_events):
        if e['id'] == storage_event['id']:
            _local_events[i] = storage_event.copy() 
            _save_to_file()
            return
    _local_events.append(storage_event.copy())
    _save_to_file()

def _load_event(event_id: str) -> Optional[Dict[str, Any]]:
    from utils.encryption import decrypt_sos_event
    raw_event = None
    if _redis:
        try:
            raw = _redis.get(_event_key(event_id))
            if raw: raw_event = json.loads(raw)
        except Exception: pass
    if not raw_event:
        raw_event = next((e for e in _local_events if e['id'] == event_id), None)
    if raw_event: return decrypt_sos_event(raw_event)
    return None

def _map_event_to_res(e: Dict[str, Any]) -> Dict[str, Any]:
    lat = e.get("lat") or 0.0
    lng = e.get("lng") or 0.0
    return {
        "id": str(e.get("id", "")), "lat": lat, "lng": lng,
        "name": e.get("name"), "phone": e.get("phone"), "email": e.get("email"),
        "extra": e.get("extra"), "trip": e.get("trip"), "status": e.get("status", "unknown"),
        "priority": e.get("priority", "low"), "category": e.get("category", "unknown"),
        "triggered_at": e.get("triggered_at", datetime.utcnow().isoformat()), 
        "google_maps_url": e.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
        "resolved_at": e.get("resolved_at"), "acknowledged_at": e.get("acknowledged_at"),
        "escalation_level": e.get("escalation_level", 1), "call_logs": e.get("call_logs", []),
        "structured_info": e.get("structured_info", {}), "active_participants": e.get("active_participants", []),
        "location_history": e.get("location_history", [])
    }

# --- STATIC ROUTES (Place these ABOVE parameter routes) ---

@router.get('/all', response_model=List[SOSEventResponse])
async def get_all_sos():
    ids = []
    if _redis:
        try:
            raw_ids = _redis.smembers(SOS_INDEX_KEY) or []
            ids = [i.decode('utf-8') if isinstance(i, bytes) else i for i in raw_ids]
        except Exception: pass
    if not ids: return [_map_event_to_res(e) for e in _local_events]
    events = []
    for eid in ids:
        e = _load_event(eid)
        if e: events.append(_map_event_to_res(e))
    return events

@router.get("/risk-check")
async def check_location_risk(lat: float, lng: float):
    from services.emergency.risk_service import risk_service
    return risk_service.check_area_risk(lat, lng)

@router.post('/confirm-safe')
async def confirm_passenger_safe(token: str):
    from utils.tracking_links import tracking_link_gen
    event_id = tracking_link_gen.verify_token(token)
    if not event_id: raise HTTPException(status_code=400, detail="Invalid token.")
    event = _load_event(event_id)
    if event:
        event["status"] = "resolved"
        event["resolved_at"] = datetime.utcnow().isoformat()
        _save_event(event)
        await manager.broadcast_sos(event)
    return {"status": "success"}

@router.get('/health')
async def health(): return {"status": "ok"}

# --- PARAMETER ROUTES (e.g. /{event_id}) ---

@router.post('/')
async def trigger_sos(request: Request, payload: SOSPayload):
    event_id = str(uuid.uuid4())
    new_event = {
        "id": event_id, "lat": payload.lat, "lng": payload.lng,
        "name": payload.name, "phone": payload.phone, "email": payload.email,
        "extra": payload.extra, "trip": payload.trip.dict() if payload.trip else None,
        "chat_history": payload.chat_history, "status": "active", "priority": "high",
        "triggered_at": datetime.utcnow().isoformat(),
    }
    from services.emergency.connectivity_service import connectivity_service
    dead_zones = connectivity_service.check_upcoming_dead_zones(payload.lat, payload.lng)
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(new_event)
    _save_event(enriched)
    return _map_event_to_res(enriched)

@router.post('/{event_id}/acknowledge')
async def acknowledge_sos(event_id: str):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    event['status'] = 'responding'
    _save_event(event)
    await manager.broadcast_sos(event)
    return _map_event_to_res(event)

@router.post('/{event_id}/resolve')
async def resolve_sos(event_id: str):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    event['status'] = 'resolved'
    event['resolved_at'] = datetime.utcnow().isoformat()
    _save_event(event)
    await manager.broadcast_sos(event)
    return _map_event_to_res(event)

@router.get('/{event_id}/report')
async def get_incident_report(event_id: str):
    from services.emergency.reporting_service import reporting_service
    report = reporting_service.generate_incident_summary(event_id)
    if not report: raise HTTPException(status_code=404)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(report)

@router.post("/{event_id}/battery") # Simplified path
async def update_battery_status(event_id: str, battery_level: float = Body(...), lat: float = Body(...), lng: float = Body(...)):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    event["battery_level"] = battery_level
    if battery_level < 0.03:
        event["ui_mode_hint"] = "TEXT_ONLY_LOW_POWER"
        event["extra"] = f"{event.get('extra', '')} | LAST BREATH"
        
    _save_event(event)
    await manager.broadcast_sos(event)
    return {"status": "ok", "hint": event.get("ui_mode_hint", "NORMAL")}
