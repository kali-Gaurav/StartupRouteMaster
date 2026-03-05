from fastapi import APIRouter, HTTPException, Request, Body, Depends, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import logging
import json
import os
import httpx
import zlib
import base64
import shutil

# create logger for this module
logger = logging.getLogger(__name__)

from database.models import User
from api.dependencies import get_optional_user
from services.cache_service import cache_service
from api.websockets import manager
from services.emergency.alert_manager import EmergencyAlertManager
from utils.limiter import limiter

router = APIRouter(tags=["sos"])

# Use the singleton instance directly
_redis = cache_service.redis
_local_events: List[Dict[str, Any]] = []
SOS_KEY_PREFIX = "sos:event:"
SOS_INDEX_KEY = "sos:events"
SOS_STREAM_KEY = "sos:stream:priority" # Task 7
PNR_REGISTRY_KEY = "sos:registry:pnr" # Task 3: O(1) PNR lookup
EMERGENCY_FILE_CACHE = "emergency_cache.json"
MEDIA_DIR = os.path.join("media", "sos")

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

def _compress(data: Any) -> str:
    """Compress data using zlib and encode to base64 string."""
    if not data: return None
    try:
        json_bytes = json.dumps(data).encode('utf-8')
        compressed = zlib.compress(json_bytes)
        return "c:" + base64.b64encode(compressed).decode('utf-8')
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return None

def _decompress(compressed_str: str) -> Any:
    """Decompress base64 string using zlib."""
    if not compressed_str or not compressed_str.startswith("c:"):
        return compressed_str
    try:
        raw_b64 = compressed_str[2:]
        compressed_bytes = base64.b64decode(raw_b64)
        json_bytes = zlib.decompress(compressed_bytes)
        return json.loads(json_bytes.decode('utf-8'))
    except Exception as e:
        logger.error(f"Decompression error: {e}")
        return None

# --- Models ---
class SOSTrip(BaseModel):
    pnr_number: Optional[str] = None # Task 3
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
    accel_g_force: Optional[float] = 0.0 # Task 17: Sensor Fusion
    impact_duration_ms: Optional[int] = 0 # Task 19: Heuristics
    post_impact_motion: Optional[float] = 1.0 # 0.0 = Stillness
    pre_trigger_transcript: Optional[str] = None # Task 21: Pre-SOS context

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
    chat_history: Optional[List[Dict[str, str]]] = []
    structured_info: Optional[Dict[str, Any]] = {}
    active_participants: Optional[List[str]] = []
    location_history: Optional[List[Dict[str, Any]]] = []

# --- Internal Helpers ---
def _event_key(event_id: str) -> str:
    return f"{SOS_KEY_PREFIX}{event_id}"

def _save_event(event: Dict[str, Any]):
    """
    Saves event to Redis and Local Memory.
    Task 6: Encrypts and Compresses for storage.
    """
    from utils.encryption import encrypt_sos_event
    redis_inst = cache_service.redis
    
    # 1. Encrypt first
    storage_event = encrypt_sos_event(event)
    
    # 2. Compress the heavy fields IN STORAGE VERSION ONLY
    if storage_event.get("chat_history") and isinstance(storage_event["chat_history"], list):
        storage_event["chat_history"] = _compress(storage_event["chat_history"])
    if storage_event.get("call_logs") and isinstance(storage_event["call_logs"], list):
        storage_event["call_logs"] = _compress(storage_event["call_logs"])

    # 3. Save to Redis
    if redis_inst:
        try:
            redis_inst.set(_event_key(storage_event['id']), json.dumps(storage_event))
            redis_inst.sadd(SOS_INDEX_KEY, storage_event['id'])
            trip = storage_event.get("trip")
            if trip and trip.get("pnr_number"):
                redis_inst.hset(PNR_REGISTRY_KEY, str(trip.get("pnr_number")), storage_event['id'])
            # Task 7: Redis Stream Publishing
            redis_inst.xadd(SOS_STREAM_KEY, {"event_id": storage_event['id'], "priority": storage_event['priority'], "data": json.dumps(storage_event)})
        except Exception: pass
        
    # 4. Save to Local Memory (Task 6: Keep uncompressed in RAM for API performance)
    global _local_events
    for i, e in enumerate(_local_events):
        if e['id'] == event['id']:
            _local_events[i] = event.copy()
            _save_to_file()
            return
    _local_events.append(event.copy())
    _save_to_file()

def _load_event(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Loads event and Task 6: Decompresses/Decrypts it.
    """
    from utils.encryption import decrypt_sos_event
    raw_event = None
    if _redis:
        try:
            raw = _redis.get(_event_key(event_id))
            if raw: raw_event = json.loads(raw)
        except Exception: pass
    if not raw_event:
        raw_event = next((e for e in _local_events if e['id'] == event_id), None)
    
    if raw_event:
        chat_data = raw_event.get("chat_history")
        if isinstance(chat_data, str) and chat_data.startswith("c:"):
            raw_event["chat_history"] = _decompress(chat_data)
        call_data = raw_event.get("call_logs")
        if isinstance(call_data, str) and call_data.startswith("c:"):
            raw_event["call_logs"] = _decompress(call_data)
        return decrypt_sos_event(raw_event)
    return None

def _map_event_to_res(e: Dict[str, Any]) -> Dict[str, Any]:
    lat = e.get("lat") or 0.0
    lng = e.get("lng") or 0.0
    
    chat_h = e.get("chat_history")
    if isinstance(chat_h, str) and chat_h.startswith("c:"):
        chat_h = _decompress(chat_h)
    elif not chat_h:
        chat_h = []
    
    call_l = e.get("call_logs")
    if isinstance(call_l, str) and call_l.startswith("c:"):
        call_l = _decompress(call_l)
    elif not call_l:
        call_l = []

    # Task 5: Deltas
    raw_history = e.get("location_history", [])
    decoded_history = []
    if raw_history:
        anchor = raw_history[0]
        decoded_history.append(anchor)
        base_lat, base_lng = anchor.get("lat"), anchor.get("lng")
        if base_lat is not None and base_lng is not None:
            try:
                base_ts = datetime.fromisoformat(anchor.get("ts"))
                for point in raw_history[1:]:
                    if point.get("is_delta"):
                        decoded_history.append({
                            "lat": round(base_lat + point["dl"], 6),
                            "lng": round(base_lng + point["dg"], 6),
                            "ts": (base_ts + timedelta(seconds=point["dt"])).isoformat(),
                            "is_decoded": True
                        })
                    else:
                        decoded_history.append(point)
            except:
                decoded_history = raw_history

    return {
        "id": str(e.get("id", "")), "lat": lat, "lng": lng,
        "name": e.get("name"), "phone": e.get("phone"), "email": e.get("email"),
        "extra": e.get("extra"), "trip": e.get("trip"), "status": e.get("status", "unknown"),
        "priority": e.get("priority", "low"), "category": e.get("category", "unknown"),
        "triggered_at": e.get("triggered_at", datetime.utcnow().isoformat()), 
        "google_maps_url": e.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
        "resolved_at": e.get("resolved_at"), "acknowledged_at": e.get("acknowledged_at"),
        "escalation_level": e.get("escalation_level", 1), 
        "call_logs": call_l,
        "chat_history": chat_h,
        "structured_info": e.get("structured_info", {}), "active_participants": e.get("active_participants", []),
        "location_history": decoded_history
    }

# --- ROUTES ---

@router.get('/{event_id}')
async def get_sos_by_id(event_id: str):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404, detail="Incident not found.")
    return _map_event_to_res(event)

@router.get('/all')
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

@router.get('/pnr/{pnr}')
async def get_sos_by_pnr(pnr: str):
    if _redis:
        try:
            event_id = _redis.hget(PNR_REGISTRY_KEY, str(pnr))
            if event_id:
                event_id = event_id.decode('utf-8') if isinstance(event_id, bytes) else event_id
                event = _load_event(event_id)
                if event and event.get("status") in ["active", "responding"]:
                    return _map_event_to_res(event)
        except Exception: pass
    for e in _local_events:
        trip = e.get("trip")
        if trip and str(trip.get("pnr_number")) == str(pnr):
            if e.get("status") in ["active", "responding"]:
                return _map_event_to_res(e)
    raise HTTPException(status_code=404, detail="No active SOS for this PNR.")

@router.post('/')
async def trigger_sos(request: Request, payload: SOSPayload):
    # Task 9: Rapid False-Alarm Rejection
    from utils.bloom_filter import sos_bloom_filter
    if payload.phone and sos_bloom_filter.is_blocked(payload.phone):
        logger.warning(f"🚫 [BLOOM FILTER] Rejecting blocked phone: {payload.phone}")
        raise HTTPException(status_code=403, detail="Safety filter rejection.")

    event_id = str(uuid.uuid4())
    new_event = {
        "id": event_id, "lat": payload.lat, "lng": payload.lng,
        "name": payload.name, "phone": payload.phone, "email": payload.email,
        "extra": payload.extra, "trip": payload.trip.dict() if payload.trip else None,
        "chat_history": payload.chat_history or [], "status": "active", "priority": "high",
        "triggered_at": datetime.utcnow().isoformat(),
        "accel_g_force": payload.accel_g_force,
        "impact_duration_ms": payload.impact_duration_ms,
        "post_impact_motion": payload.post_impact_motion,
        "pre_trigger_transcript": payload.pre_trigger_transcript
    }
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(new_event)
    
    # Task 13: Ping Freq
    train_speed = 80
    if enriched.get("railway_context", {}).get("current_station"): train_speed = 10
    if train_speed > 100: enriched["ping_interval_ms"] = 15000
    elif train_speed < 20: enriched["ping_interval_ms"] = 120000
    else: enriched["ping_interval_ms"] = 30000

    res = _map_event_to_res(enriched)
    res["ping_interval_ms"] = enriched["ping_interval_ms"]
    
    # Task 20: Auto-Dim
    now = datetime.utcnow()
    is_night = now.hour >= 23 or now.hour <= 4
    res["auto_dim_screen"] = (enriched.get("battery_level", 1.0) < 0.15) or is_night
    
    _save_event(enriched)
    return res

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
    if _redis:
        try:
            trip = event.get("trip")
            if trip and trip.get("pnr_number"):
                _redis.hdel(PNR_REGISTRY_KEY, str(trip.get("pnr_number")))
        except Exception: pass
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

@router.post("/{event_id}/battery")
async def update_battery_status(event_id: str, battery_level: float = Body(...), lat: float = Body(...), lng: float = Body(...), is_last_breath: bool = Body(False)):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    if is_last_breath or battery_level < 0.02:
        event["extra"] = f"{event.get('extra', '')} | 💀 LAST BREATH SYNC"
        event["status"] = "active"
        event["priority"] = "critical"
        _save_event(event)
        await manager.broadcast_sos(event)
        return {"status": "last_breath_acknowledged"}

    event["lat"], event["lng"], event["battery_level"] = lat, lng, battery_level
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(event)
    
    # Power optimization
    if battery_level < 0.03: enriched["keepalive_ms"] = 300000
    elif battery_level < 0.15: enriched["keepalive_ms"] = 120000
    else: enriched["keepalive_ms"] = 30000

    _save_event(enriched)
    await manager.broadcast_sos(enriched)
    
    now = datetime.utcnow()
    is_night = now.hour >= 23 or now.hour <= 4
    
    return {
        "status": "ok", "hint": enriched.get("ui_mode_hint", "NORMAL"), 
        "keepalive_ms": enriched.get("keepalive_ms", 30000),
        "ping_interval_ms": enriched.get("ping_interval_ms", 30000),
        "auto_dim_screen": (battery_level < 0.15) or is_night
    }

@router.post("/{event_id}/voice-note")
async def upload_voice_note(event_id: str, file: UploadFile = File(...)):
    """Task 35: Refinement - WhatsApp-style Push-to-Talk Voice Notes."""
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    # 1. Create storage directory
    event_media_dir = os.path.join(MEDIA_DIR, event_id)
    os.makedirs(event_media_dir, exist_ok=True)
    
    # 2. Save the file
    file_path = os.path.join(event_media_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. Generate Mock Transcript (Task 35.3)
    mock_transcript = "HELP! I need immediate assistance in coach S4."
    
    # 4. Update Event Context
    if "chat_history" not in event: event["chat_history"] = []
    event["chat_history"].append({
        "sender": "user",
        "type": "voice_note",
        "content": f"[VOICE NOTE TRANSCRIPT]: {mock_transcript}",
        "media_url": f"/media/sos/{event_id}/{file.filename}",
        "timestamp": datetime.utcnow().isoformat()
    })
    event["extra"] = f"{event.get('extra', '')} | 🎙️ New Voice Note Received."
    
    _save_event(event)
    await manager.broadcast_sos(event)
    
    return {"status": "uploaded", "transcript": mock_transcript}
