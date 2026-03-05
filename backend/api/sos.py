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
    audio_pitch_hz: Optional[float] = 150.0 # Task 24
    audio_energy: Optional[float] = 0.5 # Task 24

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
    from utils.redactor import safety_redactor
    
    lat = e.get("lat") or 0.0
    lng = e.get("lng") or 0.0
    
    chat_h = e.get("chat_history")
    if isinstance(chat_h, str) and chat_h.startswith("c:"):
        chat_h = _decompress(chat_h)
    elif not chat_h:
        chat_h = []
    
    # Task 25: Redact PII from Chat
    if isinstance(chat_h, list):
        for msg in chat_h:
            if msg.get("content"):
                msg["content"] = safety_redactor.redact(msg["content"])
    
    call_l = e.get("call_logs")
    if isinstance(call_l, str) and call_l.startswith("c:"):
        call_l = _decompress(call_l)
    elif not call_l:
        call_l = []
        
    # Task 25: Redact PII from Logs
    if isinstance(call_l, list):
        for log in call_l:
            if log.get("content"):
                log["content"] = safety_redactor.redact(log["content"])

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

    # Task 54: Safe-Zone Proximity Notification
    safe_zone_hint = None
    auth = e.get("nearest_authority")
    if auth and auth.get("distance_km") is not None:
        if auth["distance_km"] < 1.0:
            safe_zone_hint = f"HELP IS NEARBY: {auth['name']} is within {round(auth['distance_km']*1000)} meters."

    return {
        "id": str(e.get("id", "")), "lat": lat, "lng": lng,
        "name": safety_redactor.redact(e.get("name", "Unknown")), 
        "phone": safety_redactor.redact(e.get("phone", "N/A")), 
        "email": e.get("email"),
        "extra": safety_redactor.redact(e.get("extra", "")), 
        "trip": e.get("trip"), "status": e.get("status", "unknown"),
        "priority": e.get("priority", "low"), "category": e.get("category", "unknown"),
        "safe_zone_hint": safe_zone_hint, # Task 54
        "triggered_at": e.get("triggered_at", datetime.utcnow().isoformat()), 
        "google_maps_url": e.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
        "resolved_at": e.get("resolved_at"), "acknowledged_at": e.get("acknowledged_at"),
        "escalation_level": e.get("escalation_level", 1), 
        "panic_score": e.get("panic_score", 1),
        "connectivity_status": e.get("connectivity_status"), # Task 28
        "call_logs": call_l,
        "chat_history": chat_h,
        "structured_info": e.get("structured_info", {}), "active_participants": e.get("active_participants", []),
        "location_history": decoded_history
    }

# --- MODELS FOR ROUTES ---
class AdminFeedbackPayload(BaseModel):
    is_false_positive: bool
    correct_category: Optional[str] = None
    notes: Optional[str] = None

class MeshRelayPayload(BaseModel):
    original_event_id: str
    relayed_by_user_id: str
    rssi_strength: int
    data: Dict[str, Any]
    large_payload_b64: Optional[str] = None # Task 34: WiFi-Direct binary relay

# --- ROUTES ---

@router.get('/health')
async def health(): return {"status": "ok"}

@router.get('/heatmap')
async def get_incident_heatmap(precision: float = 0.1):
    """
    Task 36: Real-time Incident Visualizer (Heatmaps).
    Aggregates active incidents into a grid-based density map.
    """
    all_events = []
    ids = []
    if _redis:
        try:
            raw_ids = _redis.smembers(SOS_INDEX_KEY) or []
            ids = [i.decode('utf-8') if isinstance(i, bytes) else i for i in raw_ids]
        except Exception: pass
    
    if not ids:
        all_events = _local_events
    else:
        for eid in ids:
            e = _load_event(eid)
            if e: all_events.append(e)
            
    heatmap = {}
    for e in all_events:
        if e.get("status") in ["active", "responding"]:
            lat = round(e.get("lat", 0.0) / precision) * precision
            lng = round(e.get("lng", 0.0) / precision) * precision
            grid_key = f"{round(lat, 2)},{round(lng, 2)}"
            heatmap[grid_key] = heatmap.get(grid_key, 0) + 1
            
    result = []
    for key, count in heatmap.items():
        lt, lg = map(float, key.split(","))
        result.append({"lat": lt, "lng": lg, "weight": count})
    return result

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

@router.post('/mesh-sync')
async def sync_mesh_alert(payload: MeshRelayPayload):
    existing = _load_event(payload.original_event_id)
    if payload.large_payload_b64:
        if existing: existing["extra"] = f"{existing.get('extra', '')} | 📁 HIGH-FIDELITY DATA RELAYED (WiFi-Direct)"
        else: payload.data["extra"] = f"{payload.data.get('extra', '')} | 📁 HIGH-FIDELITY DATA RELAYED (WiFi-Direct)"

    if existing:
        existing["extra"] = f"{existing.get('extra', '')} | 📡 MESH RELAY SEEN (Relay: {payload.relayed_by_user_id})"
        _save_event(existing)
        return {"status": "merged", "event_id": payload.original_event_id}
    
    event = payload.data
    event["id"] = payload.original_event_id
    event["extra"] = f"{event.get('extra', '')} | 🛰️ ORIGINATED VIA MESH (Relay: {payload.relayed_by_user_id})"
    _save_event(event)
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(event)
    _save_event(enriched)
    return {"status": "initiated_via_mesh", "event_id": payload.original_event_id}

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

@router.post('/')
async def trigger_sos(request: Request, payload: SOSPayload):
    from utils.bloom_filter import sos_bloom_filter
    if payload.phone and sos_bloom_filter.is_blocked(payload.phone):
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
        "pre_trigger_transcript": payload.pre_trigger_transcript,
        "audio_pitch_hz": payload.audio_pitch_hz,
        "audio_energy": payload.audio_energy
    }
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(new_event)
    
    res = _map_event_to_res(enriched)
    res["ping_interval_ms"] = enriched.get("ping_interval_ms", 30000)
    res["panic_score"] = enriched.get("panic_score", 1)
    res["railway_context"] = enriched.get("railway_context", {})
    res["conference_id"] = enriched.get("conference_id")
    res["pre_fetch_data"] = enriched.get("pre_fetch_data")
    res["historical_risk_level"] = enriched.get("historical_risk_level") # Task 50

    now = datetime.utcnow()

    is_night = now.hour >= 23 or now.hour <= 4
    res["auto_dim_screen"] = (enriched.get("battery_level", 1.0) < 0.15) or is_night
    # Task 44: Silent-Panic Vibration Pattern
    # [Pulse, Pause, Pulse, Pause] in ms
    if res.get("priority") == "critical":
        res["vibration_pattern"] = [100, 50, 100, 50, 500, 50, 500] # SOS in Morse-ish
    else:
        res["vibration_pattern"] = [50, 100, 50, 100] # Confirmation double-pulse
    
    # Task 46: High-Frequency GPS 'Burst' Mode
    if res.get("priority") == "critical" or res.get("panic_score", 0) >= 8:
        res["gps_burst_interval_ms"] = 2000 # 2s burst
        res["gps_burst_duration_s"] = 60
    else:
        res["gps_burst_interval_ms"] = 0 # No burst
    
    _save_event(enriched)
    return res

@router.get('/{event_id}/family-view')
async def get_sos_family_view(event_id: str):
    """
    Task 52: Dynamic Incident Redaction for Family View.
    Returns a softened, non-technical view for emergency contacts.
    """
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    # 1. Empathetic Status Mapping
    status_map = {
        "active": "Request received, locating help...",
        "responding": "Official assistance is on the way.",
        "resolved": "Passenger has confirmed they are safe.",
        "archived": "Incident concluded."
    }
    
    # 2. Redact Technical/Traumatic Data
    res = _map_event_to_res(event)
    redacted = {
        "id": res["id"],
        "status_display": status_map.get(res["status"], "Processing..."),
        "lat": res["lat"],
        "lng": res["lng"],
        "triggered_at": res["triggered_at"],
        "google_maps_url": res["google_maps_url"],
        "railway_context": {
            "current_station": res.get("railway_context", {}).get("current_station"),
            "next_station": res.get("railway_context", {}).get("next_station")
        },
        "message": "Your family member has requested assistance. Our team and nearby responders are on it."
    }
    
    return redacted

@router.get('/{event_id}/autofill')
async def get_sos_autofill(event_id: str):
    """
    Task 48: Dynamic SOS Form Autofill (AI-Assisted).
    Extracts entities from transcript to suggest form values.
    """
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    from utils.sos_entities import SOSEntityExtractor
    
    # Aggregate text context
    text_context = str(event.get("extra", ""))
    for msg in event.get("chat_history", []):
        text_context += " " + str(msg.get("content", ""))
        
    extracted = SOSEntityExtractor.extract(text_context)
    
    # Map to form fields
    suggestions = {
        "coach_id": extracted.get("coach"),
        "seat_number": extracted.get("seat") or extracted.get("berth"),
        "medical_symptoms": extracted.get("medical", []),
        "security_threat": extracted.get("weapon"),
        "suggested_category": event.get("category"),
        "urgency_score": SOSEntityExtractor.get_urgency_score(extracted)
    }
    
    return suggestions

@router.post('/{event_id}/feedback')
async def submit_admin_feedback(event_id: str, payload: AdminFeedbackPayload):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    if payload.is_false_positive and event.get("phone"):
        from utils.bloom_filter import sos_bloom_filter
        sos_bloom_filter.add(event.get("phone"))
    
    from database.session import SessionLocal
    from database.models import RLFeedbackLog, User
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.supabase_id == "ADMIN_SYSTEM").first()
        if not admin_user:
            admin_user = User(supabase_id="ADMIN_SYSTEM", email="admin@safety.com")
            db.add(admin_user)
            db.commit()
        log = RLFeedbackLog(user_id="ADMIN_SYSTEM", prompt=f"CORRECT: {event_id}", response=payload.notes, rating=1, timestamp=datetime.utcnow())
        db.add(log)
        db.commit()
    except Exception: pass
    finally: db.close()
    event["admin_feedback"] = payload.dict()
    _save_event(event)
    return {"status": "feedback_recorded"}

@router.post('/{event_id}/handshake')
async def perform_safety_handshake(event_id: str, party: str = Body(..., embed=True)):
    """
    Task 56: Multi-party Safety Handshake.
    Parties: 'victim', 'responder', 'admin'.
    Broadcasts completion when all 3 acknowledge.
    """
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    handshake = event.get("handshake_status", {"victim": False, "responder": False, "admin": False})
    if party in handshake:
        handshake[party] = True
        logger.info(f"🤝 [HANDSHAKE] Party '{party}' ready for incident {event_id}")
    
    event["handshake_status"] = handshake
    
    # Check if complete
    if all(handshake.values()):
        event["extra"] = f"{event.get('extra', '')} | 🤝 SAFE HANDSHAKE COMPLETE (All parties connected)"
        await manager.broadcast_sos({"type": "SAFE_HANDSHAKE_COMPLETE", "event_id": event_id})
        logger.info(f"✅ [HANDSHAKE] Triple-confirmation complete for incident {event_id}")

    _save_event(event)
    return {"status": "handshake_updated", "current_status": handshake}

@router.post('/{event_id}/acknowledge')
async def acknowledge_sos(event_id: str):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    event['status'] = 'responding'
    _save_event(event)
    await manager.broadcast_sos(event)
    return _map_event_to_res(event)

class DebriefPayload(BaseModel):
    rating: int # 1-5
    comment: Optional[str] = None
    emotional_state: Optional[str] = None
    language: Optional[str] = "en"
    responder_ids: Optional[List[str]] = [] # IDs of users who helped

@router.post('/{event_id}/debrief')
async def submit_passenger_debrief(event_id: str, payload: DebriefPayload):
    """
    Task 40: Multi-language Post-Incident Debrief.
    Collects feedback and rewards responders with Karma.
    """
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    # 1. Store Debrief
    event["debrief"] = payload.dict()
    event["status"] = "archived" # Move from resolved to archived
    
    # 2. Reward Responders (Task 32 integration)
    if payload.responder_ids:
        from database.session import SessionLocal
        from database.models import User, Profile
        db = SessionLocal()
        try:
            for rid in payload.responder_ids:
                prof = db.query(Profile).join(User, User.id == Profile.user_id).filter(User.supabase_id == rid).first()
                if prof:
                    prof.karma_score += 10 # Reward for helping
                    prof.help_count += 1
                    logger.info(f"🏆 [KARMA] Rewarded responder {rid} with +10 karma.")
            db.commit()
        except Exception as e:
            logger.error(f"Failed to reward responders: {e}")
        finally: db.close()
        
    _save_event(event)
    return {"status": "debrief_accepted", "message": "Thank you for your feedback. Responders have been rewarded."}

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

@router.post("/{event_id}/battery")
async def update_battery_status(event_id: str, battery_level: float = Body(...), lat: float = Body(...), lng: float = Body(...), is_last_breath: bool = Body(False), motion_level: float = Body(1.0)):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    
    # Task 55: Prolonged Stillness Heuristic
    if event.get("status") in ["active", "responding"]:
        last_motion = event.get("last_motion_level", 1.0)
        if motion_level == 0.0 and last_motion == 0.0:
            # Two pings of zero motion = Unconscious Threat
            event["priority"] = "critical"
            event["extra"] = f"{event.get('extra', '')} | 💀 ALERT: PROLONGED STILLNESS (Potential Unconsciousness)"
            logger.warning(f"🆘 [STILLNESS] Auto-escalating incident {event_id} due to zero movement.")
        event["last_motion_level"] = motion_level

    if is_last_breath or battery_level < 0.02:
        event["extra"] = f"{event.get('extra', '')} | 💀 LAST BREATH SYNC (Going Offline)"
        event["status"] = "active"
        event["priority"] = "critical"
        event["last_breath_lat"] = lat
        event["last_breath_lng"] = lng
        event["last_breath_ts"] = datetime.utcnow().isoformat()
        
        # Notify Admin via WebSocket immediately
        _save_event(event)
        await manager.broadcast_sos(event)
        
        # Task 44: Final Confirmation Pulse
        return {
            "status": "last_breath_acknowledged",
            "vibration_pattern": [1000] # Long 1s pulse
        }
    event["lat"], event["lng"], event["battery_level"] = lat, lng, battery_level
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(event)
    _save_event(enriched)
    await manager.broadcast_sos(enriched)
    return {"status": "ok", "auto_dim_screen": battery_level < 0.15}

@router.post("/{event_id}/voice-note")
async def upload_voice_note(event_id: str, file: UploadFile = File(...)):
    event = _load_event(event_id)
    if not event: raise HTTPException(status_code=404)
    event_media_dir = os.path.join(MEDIA_DIR, event_id)
    os.makedirs(event_media_dir, exist_ok=True)
    file_path = os.path.join(event_media_dir, file.filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    if "chat_history" not in event: event["chat_history"] = []
    event["chat_history"].append({"sender": "user", "type": "voice_note", "content": "[VOICE NOTE]", "media_url": f"/media/sos/{event_id}/{file.filename}", "timestamp": datetime.utcnow().isoformat()})
    _save_event(event)
    await manager.broadcast_sos(event)
    return {"status": "uploaded"}
