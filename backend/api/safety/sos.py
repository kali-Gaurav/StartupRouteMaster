# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, Request, Body, Depends, UploadFile, File
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Any, cast, Dict, List, Optional
from datetime import datetime, timedelta
import uuid
import logging
import json
import os
# pyrefly: ignore [missing-import]
import httpx
import zlib
import base64
import shutil
import asyncio

# create logger for this module
logger = logging.getLogger(__name__)

from database.models import User, SOSEvent, SOSTelemetry
from database.config import Config
from api.dependencies import get_optional_user
from services.multi_layer_cache import multi_layer_cache
from api.websockets import manager
from services.emergency.alert_manager import EmergencyAlertManager
from utils.limiter import limiter
from database.session import SessionLocal

import threading

from services.emergency.safety_service import safety_service
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from database import get_db

router = APIRouter(prefix="/sos", tags=["sos"])

class TelemetryPayload(BaseModel):
    lat: float
    lng: float
    battery_level: Optional[float] = 1.0
    speed_kmh: Optional[float] = 0.0

@router.post("/{event_id}/telemetry")
async def update_sos_telemetry(
    event_id: str, 
    payload: TelemetryPayload,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Task 4.2: Automated Route Deviant Alert & Geofencing.
    Analyzes live telemetry against the expected railway path.
    """
    event_data = await _load_event_async(event_id, db)
    if not event_data: raise HTTPException(status_code=404)
    
    # 1. Update basic state in event data (Redis/Snapshot)
    event_data["lat"] = payload.lat
    event_data["lng"] = payload.lng
    event_data["battery_level"] = payload.battery_level
    
    # 2. Persist granular telemetry point to DB
    new_telemetry = SOSTelemetry(
        event_id=event_id,
        lat=payload.lat,
        lng=payload.lng,
        battery_level=payload.battery_level,
        timestamp=datetime.utcnow()
    )
    db.add(new_telemetry)
    
    # 3. Geofencing Audit (Deep Logic)
    target_user_id = event_data.get("user_id") or (str(user.id) if user is not None else None)
    
    deviation_report = {"status": "skipped"}
    if target_user_id:
        deviation_report = await safety_service.check_journey_deviation(
            user_id=target_user_id,
            lat=payload.lat,
            lon=payload.lng,
            db_user=db
        )
    
    # 4. Handle Deviation
    if deviation_report.get("status") == "deviated":
        event_data["priority"] = "critical"
        event_data["extra"] = f"{event_data.get('extra', '')} | 🚩 GEOFENCE_VIOLATION: {deviation_report['distance_km']}km off-track"
        await manager.broadcast_sos({"type": "GEOFENCE_ALERT", "event_id": event_id, "report": deviation_report})

    await _save_event_async(event_data, db)
    db.commit()
    
    return {
        "status": "ok",
        "geofence": deviation_report,
        "is_critical": event_data.get("priority") == "critical"
    }

# Registry Keys
SOS_KEY_PREFIX = "sos:event:"
SOS_INDEX_KEY = "sos:events"
SOS_STREAM_KEY = "sos:stream:priority" # Task 7
PNR_REGISTRY_KEY = "sos:registry:pnr" # Task 3: O(1) PNR lookup

# Note: EMERGENCY_FILE_CACHE for local-json is deprecated in favor of SOSEvent tables
MEDIA_DIR = os.path.join(Config.BASE_DIR or "", "media", "sos")

def _compress(data: Any) -> Optional[str]:

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

# --- Persistence Helpers ---

def _event_key(event_id: str) -> str:
    return f"{SOS_KEY_PREFIX}{event_id}"

async def _get_redis_index_ids() -> List[str]:
    ids: List[str] = []
    if multi_layer_cache.redis:
        try:
            import redis as redis_module
            from database.config import Config

            sync_redis: Any = redis_module.from_url(Config.REDIS_URL)
            raw_ids = cast(Any, sync_redis.smembers(SOS_INDEX_KEY))
            if hasattr(raw_ids, "__await__"):
                raw_ids = await raw_ids
            raw_ids = raw_ids or []
            ids = [i.decode("utf-8") if isinstance(i, bytes) else i for i in raw_ids]
        except Exception:
            pass
    return ids

async def _get_redis_value(key: str) -> Optional[Any]:
    if multi_layer_cache.redis:
        try:
            import redis as redis_module
            from database.config import Config

            sync_redis: Any = redis_module.from_url(Config.REDIS_URL)
            value = cast(Any, sync_redis.get(key))
            if hasattr(value, "__await__"):
                value = await value
            return value
        except Exception:
            pass
    return None

async def _save_event_async(event: Dict[str, Any], db: Optional[Session] = None):
    """
    Saves event to Redis immediately and schedules a DB commit.
    Task 6: Encrypts and Compresses for storage.
    """
    from utils.encryption import encrypt_sos_event
    
    # 1. Encrypt first
    storage_event = encrypt_sos_event(event)
    
    # 2. Compress the heavy fields IN STORAGE VERSION ONLY
    if storage_event.get("chat_history") and isinstance(storage_event["chat_history"], list):
        storage_event["chat_history"] = _compress(storage_event["chat_history"])
    if storage_event.get("call_logs") and isinstance(storage_event["call_logs"], list):
        storage_event["call_logs"] = _compress(storage_event["call_logs"])

    # 3. Save to Multi-Layer Cache (L1 + L2)
    # Using 'put' instead of non-existent 'set_sync'
    await multi_layer_cache.put(_event_key(storage_event['id']), storage_event, ttl=86400 * 3) # 3 Day TTL
    
    # 4. Update Index & Registry in Redis
    if multi_layer_cache.redis:
        try:
            await multi_layer_cache.redis.sadd(SOS_INDEX_KEY, storage_event['id'])
            trip = storage_event.get("trip")
            if trip and trip.get("pnr_number"):
                await multi_layer_cache.redis.setex(f"{PNR_REGISTRY_KEY}:{trip.get('pnr_number')}", 86400 * 7, storage_event['id'])
        except Exception as e:
            logger.error(f"Redis Index Update Failed: {e}")

    # 5. Background DB Persistence (Production Sync)
    # We use a non-blocking task but inside the same loop to avoid thread-exhaustion
    async def _async_persist():
        # Use provided DB session if available, else create one
        _db = db or SessionLocal()
        try:
            sos_record = _db.query(SOSEvent).filter(SOSEvent.id == event['id']).first()
            if not sos_record:
                sos_record = SOSEvent(id=event['id'])
                _db.add(sos_record)
            
            # Sync fields (Directly from decrypted event)
            sos_record.user_id = cast(Any, event.get("user_id"))
            status_value = cast(Any, event.get("status", "ACTIVE"))
            sos_record.status = cast(Any, status_value.upper())
            priority_value = cast(Any, event.get("priority", "high"))
            sos_record.priority = cast(Any, priority_value)
            if event.get("category") is not None:
                sos_record.category = cast(Any, event["category"])
            if event.get("extra") is not None:
                sos_record.extra = cast(Any, event["extra"])
            if event.get("name") is not None:
                sos_record.name = cast(Any, event["name"])
            if event.get("phone") is not None:
                sos_record.phone = cast(Any, event["phone"])
            if event.get("email") is not None:
                sos_record.email = cast(Any, event["email"])
            if event.get("lat") is not None:
                sos_record.lat = cast(Any, float(event["lat"]))
            if event.get("lng") is not None:
                sos_record.lng = cast(Any, float(event["lng"]))
            
            # Use JSON fields for lists
            sos_record.call_logs = cast(Any, event.get("call_logs", []))
            sos_record.chat_history = cast(Any, event.get("chat_history", []))
            sos_record.structured_info = cast(Any, event.get("structured_info", {}))
            sos_record.active_participants = cast(Any, event.get("active_participants", []))
            sos_record.trip_data = cast(Any, event.get("trip", {}))
            
            if event.get("triggered_at"):
                try:
                    sos_record.triggered_at = cast(Any, datetime.fromisoformat(event["triggered_at"]))
                except Exception:
                    pass
            if event.get("resolved_at"):
                try:
                    sos_record.resolved_at = cast(Any, datetime.fromisoformat(event["resolved_at"]))
                except Exception:
                    pass
            if event.get("acknowledged_at"):
                try:
                    sos_record.acknowledged_at = cast(Any, datetime.fromisoformat(event["acknowledged_at"]))
                except Exception:
                    pass
            
            _db.commit()
            logger.debug(f"💾 [DB_SYNC] SOSEvent {event['id']} persisted.")
        except Exception as e:
            logger.error(f"DB persistence failed for {event.get('id')}: {e}")
        finally:
            if not db:
                _db.close() # Close only if we created it

    asyncio.create_task(_async_persist())

async def _load_event_async(event_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Loads event from Redis or Postgres and Task 6: Decompresses/Decrypts it.
    """
    from utils.encryption import decrypt_sos_event
    
    # 1. Try Redis
    raw_event = None
    if multi_layer_cache.redis:
        try:
            raw = await multi_layer_cache.get(_event_key(event_id))
            if raw: raw_event = raw
        except Exception:
            pass

    _db = db or SessionLocal()
    try:
        # 2. Try Postgres Fallback
        if not raw_event:
            sos_record = _db.query(SOSEvent).filter(SOSEvent.id == event_id).first()
            if sos_record:
                raw_event = {
                "id": sos_record.id,
                "user_id": sos_record.user_id,
                "status": sos_record.status.lower(),
                "priority": sos_record.priority,
                "category": sos_record.category,
                "extra": sos_record.extra,
                "name": sos_record.name,
                "phone": sos_record.phone,
                "email": sos_record.email,
                "lat": sos_record.lat,
                "lng": sos_record.lng,
                "call_logs": sos_record.call_logs,
                "chat_history": sos_record.chat_history,
                "structured_info": sos_record.structured_info,
                "active_participants": sos_record.active_participants,
                "trip": sos_record.trip_data,
                "triggered_at": sos_record.triggered_at.isoformat(),
                "resolved_at": (cast(Any, sos_record.resolved_at).isoformat() if cast(Any, sos_record.resolved_at) else None),
                "acknowledged_at": (cast(Any, sos_record.acknowledged_at).isoformat() if cast(Any, sos_record.acknowledged_at) else None)
            }
    finally:
        if not db:
            _db.close()

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
async def get_incident_heatmap(precision: float = 0.1, db: Session = Depends(get_db)):
    """
    Task 36: Real-time Incident Visualizer (Heatmaps).
    Aggregates active incidents into a grid-based density map.
    """
    all_events = []
    ids = await _get_redis_index_ids()
    
    if not ids:
        # Fallback: Query all active events from DB
        active_records = db.query(SOSEvent).filter(SOSEvent.status.in_(["ACTIVE", "RESPONDING"])).all()
        ids = [str(r.id) for r in active_records]
    
    for eid in ids:
        e = await _load_event_async(eid, db)
        if e is not None:
            all_events.append(e)

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
async def get_sos_by_pnr(pnr: str, db: Session = Depends(get_db)):
    event_id = await _get_redis_value(f"{PNR_REGISTRY_KEY}:{pnr}")
    if event_id:
        if isinstance(event_id, bytes):
            event_id = event_id.decode('utf-8')
        event = await _load_event_async(str(event_id), db)
        if event and event.get("status") in ["active", "responding"]:
            return _map_event_to_res(event)

    # DB Fallback for PNR (Search in JSON trip_data)
    event_record = db.query(SOSEvent).filter(
        sa.or_(
            SOSEvent.status == "ACTIVE",
            SOSEvent.status == "RESPONDING"
        )
    ).all()
    
    for r in event_record:
        trip_data = r.trip_data
        if isinstance(trip_data, dict) and str(trip_data.get("pnr_number")) == str(pnr):
            event = await _load_event_async(str(r.id), db)
            if event is not None:
                return _map_event_to_res(event)

    raise HTTPException(status_code=404, detail="No active SOS for this PNR.")

@router.get('/all')
async def get_all_sos(db: Session = Depends(get_db)):
    ids = await _get_redis_index_ids()

    if not ids:
        active_records = db.query(SOSEvent).filter(SOSEvent.status.in_( ["ACTIVE", "RESPONDING"] ) ).all()
        ids = [str(r.id) for r in active_records]

    events = []
    for eid in ids:
        e = await _load_event_async(str(eid), db)
        if e is not None:
            events.append(_map_event_to_res(e))
    return events

@router.get("/risk-check")
async def check_location_risk(lat: float, lng: float):
    from services.emergency.risk_service import risk_service
    return risk_service.check_area_risk(lat, lng)

@router.get('/{event_id}')
async def get_sos_by_id(event_id: str, db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404, detail="Incident not found.")
    return _map_event_to_res(event)

@router.post('/mesh-sync')
async def sync_mesh_alert(payload: MeshRelayPayload, db: Session = Depends(get_db)):
    existing = await _load_event_async(payload.original_event_id, db)
    if payload.large_payload_b64:
        if existing: existing["extra"] = f"{existing.get('extra', '')} | 📁 HIGH-FIDELITY DATA RELAYED (WiFi-Direct)"
        else: payload.data["extra"] = f"{payload.data.get('extra', '')} | 📁 HIGH-FIDELITY DATA RELAYED (WiFi-Direct)"

    if existing:
        existing["extra"] = f"{existing.get('extra', '')} | 📡 MESH RELAY SEEN (Relay: {payload.relayed_by_user_id})"
        await _save_event_async(existing)
        return {"status": "merged", "event_id": payload.original_event_id}
    
    event = payload.data
    event["id"] = payload.original_event_id
    event["extra"] = f"{event.get('extra', '')} | 🛰️ ORIGINATED VIA MESH (Relay: {payload.relayed_by_user_id})"
    await _save_event_async(event)
    alert_mgr = EmergencyAlertManager()
    enriched = await alert_mgr.process_sos_alert(event)
    await _save_event_async(enriched)
    return {"status": "initiated_via_mesh", "event_id": payload.original_event_id}

@router.post('/confirm-safe')
async def confirm_passenger_safe(token: str, db: Session = Depends(get_db)):
    from utils.tracking_links import tracking_link_gen
    event_id = tracking_link_gen.verify_token(token)
    if not event_id: raise HTTPException(status_code=400, detail="Invalid token.")
    event = await _load_event_async(event_id, db)
    if event:
        event["status"] = "resolved"
        event["resolved_at"] = datetime.utcnow().isoformat()
        await _save_event_async(event)
        await manager.broadcast_sos(event)
    return {"status": "success"}

@router.post('/')
async def trigger_sos(request: Request, payload: SOSPayload, user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_db)):
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
        "user_id": user.id if user else None,
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
    if res.get("priority") == "critical":
        res["vibration_pattern"] = [100, 50, 100, 50, 500, 50, 500] 
    else:
        res["vibration_pattern"] = [50, 100, 50, 100] 
    
    # Task 46: High-Frequency GPS 'Burst' Mode
    if res.get("priority") == "critical" or res.get("panic_score", 0) >= 8:
        res["gps_burst_interval_ms"] = 2000 # 2s burst
        res["gps_burst_duration_s"] = 60
    else:
        res["gps_burst_interval_ms"] = 0 
    
    await _save_event_async(enriched)

    # ── [Feature D] Corridor Safety Bus: Publish live alert to routing engine ──
    try:
        from core.route_engine.corridor_safety_bus import publish_sos_alert
        railway_ctx = enriched.get("railway_context", {})
        affected_stations = []

        # Add current station if known
        current_stn = railway_ctx.get("current_station") or railway_ctx.get("nearest_station")
        if current_stn:
            affected_stations.append(str(current_stn).upper())

        # Add origin from trip if available
        if enriched.get("trip") and enriched["trip"].get("origin"):
            affected_stations.append(str(enriched["trip"]["origin"]).upper())

        if affected_stations:
            severity = "CRITICAL" if res.get("priority") == "critical" else "WARNING"
            duration = 3.0 if severity == "CRITICAL" else 1.5
            publish_sos_alert(
                sos_id=event_id,
                affected_stations=affected_stations,
                severity=severity,
                message=f"SOS triggered: {enriched.get('category', 'UNKNOWN')} at {affected_stations}",
                duration_hours=duration,
            )
            logger.warning(f"🚨 [SOS→SafetyBus] Alert published: {severity} at {affected_stations}")
    except Exception as _sb_ex:
        logger.warning(f"[SOS] Safety Bus publish failed (non-fatal): {_sb_ex}")

    return res

@router.get('/{event_id}/family-view')
async def get_sos_family_view(event_id: str, db: Session = Depends(get_db)):
    """
    Task 52: Dynamic Incident Redaction for Family View.
    Returns a softened, non-technical view for emergency contacts.
    """
    event = await _load_event_async(event_id, db)
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
async def get_sos_autofill(event_id: str, db: Session = Depends(get_db)):
    """
    Task 48: Dynamic SOS Form Autofill (AI-Assisted).
    Extracts entities from transcript to suggest form values.
    """
    event = await _load_event_async(event_id, db)
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
async def submit_admin_feedback(event_id: str, payload: AdminFeedbackPayload, db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404)
    if payload.is_false_positive and event.get("phone"):
        from utils.bloom_filter import sos_bloom_filter
        sos_bloom_filter.add(event.get("phone"))
    
    from database.models import RLFeedbackLog, User
    try:
        admin_user = db.query(User).filter(User.firebase_uid == "ADMIN_SYSTEM").first()
        if not admin_user:
            admin_user = User(firebase_uid="ADMIN_SYSTEM", email="admin@safety.com")
            db.add(admin_user)
            db.commit()
        log = RLFeedbackLog(user_id="ADMIN_SYSTEM", prompt=f"CORRECT: {event_id}", response=payload.notes, rating=1, timestamp=datetime.utcnow())
        db.add(log)
        db.commit()
    except Exception: pass
    
    event["admin_feedback"] = payload.dict()
    await _save_event_async(event)
    return {"status": "feedback_recorded"}

@router.post('/{event_id}/handshake')
async def perform_safety_handshake(event_id: str, party: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """
    Task 56: Multi-party Safety Handshake.
    Parties: 'victim', 'responder', 'admin'.
    Broadcasts completion when all 3 acknowledge.
    """
    event = await _load_event_async(event_id, db)
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

    await _save_event_async(event)
    return {"status": "handshake_updated", "current_status": handshake}

@router.post('/{event_id}/acknowledge')
async def acknowledge_sos(event_id: str, db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404)
    event['status'] = 'responding'
    event['acknowledged_at'] = datetime.utcnow().isoformat()
    await _save_event_async(event)
    await manager.broadcast_sos(event)
    return _map_event_to_res(event)

class DebriefPayload(BaseModel):
    rating: int # 1-5
    comment: Optional[str] = None
    emotional_state: Optional[str] = None
    language: Optional[str] = "en"
    responder_ids: Optional[List[str]] = [] # IDs of users who helped

@router.post('/{event_id}/debrief')
async def submit_passenger_debrief(event_id: str, payload: DebriefPayload, db: Session = Depends(get_db)):
    """
    Task 40: Multi-language Post-Incident Debrief.
    Collects feedback and rewards responders with Karma.
    """
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404)
    
    # 1. Store Debrief
    event["debrief"] = payload.dict()
    event["status"] = "archived" # Move from resolved to archived
    
    # 2. Reward Responders (Task 32 integration)
    if payload.responder_ids:
        from database.models import User, Profile
        try:
            for rid in payload.responder_ids:
                updated = db.query(Profile).join(User, User.id == Profile.user_id).filter(User.firebase_uid == rid).update(
                    {
                        "karma_score": Profile.karma_score + 10,
                        "help_count": Profile.help_count + 1,
                    },
                    synchronize_session=False
                )
                if updated:
                    logger.info(f"🏆 [KARMA] Rewarded responder {rid} with +10 karma.")
            db.commit()
        except Exception as e:
            logger.error(f"Failed to reward responders: {e}")
        
    await _save_event_async(event)
    return {"status": "debrief_accepted", "message": "Thank you for your feedback. Responders have been rewarded."}

@router.post('/{event_id}/resolve')
async def resolve_sos(event_id: str, db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404)
    event['status'] = 'resolved'
    event['resolved_at'] = datetime.utcnow().isoformat()
    if multi_layer_cache.redis:
        try:
            import redis
            from database.config import Config
            sync_redis = redis.from_url(Config.REDIS_URL)
            trip = event.get("trip")
            if trip and trip.get("pnr_number"):
                sync_redis.delete(f"{PNR_REGISTRY_KEY}:{trip.get('pnr_number')}")
        except Exception: pass
    await _save_event_async(event)
    await manager.broadcast_sos(event)
    return _map_event_to_res(event)

@router.post("/{event_id}/battery")
async def update_battery_status(event_id: str, battery_level: float = Body(...), lat: float = Body(...), lng: float = Body(...), is_last_breath: bool = Body(False), motion_level: float = Body(1.0), db: Session = Depends(get_db)):
    event_data = await _load_event_async(event_id, db)
    if not event_data: raise HTTPException(status_code=404)
    
    # Task 5.16: High-frequency state update (Zero overhead)
    event_data["lat"], event_data["lng"], event_data["battery_level"] = lat, lng, battery_level
    event_data["last_motion_level"] = motion_level
    
    if is_last_breath or battery_level < 0.02:
        event_data["priority"] = "critical"
        event_data["extra"] = f"{event_data.get('extra', '')} | 💀 LAST BREATH SYNC"

    # Task 5.17: Throttled Enrichment (Max once every 10 seconds)
    now_ts = datetime.utcnow().timestamp()
    last_sync = event_data.get("_last_background_sync", 0)
    
    if now_ts - last_sync > 10: # 10s throttle
        event_data["_last_background_sync"] = now_ts
        async def background_update():
            try:
                from services.emergency.alert_manager import EmergencyAlertManager
                alert_mgr = EmergencyAlertManager()
                await alert_mgr.process_sos_alert(event_data)
                # Redis update is handled via process_sos_alert calling save? 
                # Actually, we should call save after enrichment
                await _save_event_async(event_data)
            except Exception as e:
                logger.error(f"Background battery update failed: {e}")
        asyncio.create_task(background_update())
    else:
        # Just broadcast for UI and sync to Redis for quick lookups
        await _save_event_async(event_data)
        await manager.broadcast_sos(event_data)

    return {"status": "ok", "auto_dim_screen": battery_level < 0.15}

@router.post("/{event_id}/voice-note")
async def upload_voice_note(event_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event: raise HTTPException(status_code=404)
    event_media_dir = os.path.join(str(MEDIA_DIR), event_id)
    os.makedirs(event_media_dir, exist_ok=True)
    import werkzeug.utils
    filename = werkzeug.utils.secure_filename(cast(str, file.filename))
    if not filename:
        filename = f"voice_note_{int(time.time())}.audio"
    file_path = os.path.join(event_media_dir, filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    if "chat_history" not in event: event["chat_history"] = []
    event["chat_history"].append({"sender": "user", "type": "voice_note", "content": "[VOICE NOTE]", "media_url": f"/media/sos/{event_id}/{filename}", "timestamp": datetime.utcnow().isoformat()})
    await _save_event_async(event)
    await manager.broadcast_sos(event)
    return {"status": "uploaded"}
