from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

# create logger for this module
logger = logging.getLogger(__name__)

from services.cache_service import cache_service
from api.websockets import manager
from services.emergency.alert_manager import EmergencyAlertManager
# Usered limiter from its source module
from utils.limiter import limiter

# HTTP client for calling other internal services
import os
import httpx

NOTIFICATION_URL = os.getenv("NOTIFICATION_URL")
EMERGENCY_ADMIN_NUMBER = os.getenv("EMERGENCY_ADMIN_NUMBER")  # optional phone/email for admins

router = APIRouter(prefix="/api/sos", tags=["sos"])

_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_events: List[Dict[str, Any]] = []
SOS_KEY_PREFIX = "sos:event:"
SOS_INDEX_KEY = "sos:events"

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
    triggered_at: str
    google_maps_url: str
    resolved_at: Optional[str] = None


def _event_key(event_id: str) -> str:
    return f"{SOS_KEY_PREFIX}{event_id}"


def _save_event(event: Dict[str, Any]):
    if _redis:
        try:
            import json
            _redis.set(_event_key(event['id']), json.dumps(event))
            _redis.sadd(SOS_INDEX_KEY, event['id'])
            return
        except Exception:
            pass
    _local_events.append(event)


def _load_event(event_id: str) -> Optional[Dict[str, Any]]:
    if _redis:
        try:
            raw = _redis.get(_event_key(event_id))
            if raw:
                import json
                return json.loads(raw)
        except Exception:
            pass
    for e in _local_events:
        if e['id'] == event_id:
            return e
    return None


from core.monitoring import SOS_ALERTS_TOTAL, GUARDIAN_MODE_ACTIVATIONS

@router.post('/', response_model=SOSEventResponse)
@limiter.limit("5/minute")
async def trigger_sos(request: Request, payload: SOSPayload):
    # Track metrics
    is_guardian = payload.trip and payload.trip.mode == "GUARDIAN"
    if is_guardian:
        GUARDIAN_MODE_ACTIVATIONS.inc()
    
    SOS_ALERTS_TOTAL.labels(
        severity="high" if not is_guardian else "medium", 
        status="active"
    ).inc()

    event_id = str(uuid.uuid4())
    new_event = {
        "id": event_id,
        "lat": payload.lat,
        "lng": payload.lng,
        "name": payload.name,
        "phone": payload.phone,
        "email": payload.email,
        "extra": payload.extra,
        "trip": payload.trip.dict() if payload.trip else None,
        "status": "active",
        "priority": "high",
        "triggered_at": datetime.utcnow().isoformat(),
        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={payload.lat},{payload.lng}",
    }
    _save_event(new_event)
    
    # Enrich with Railway Intelligence and broadcast via Phase 12 WebSocket Manager
    alert_mgr = EmergencyAlertManager()
    enriched_event = await alert_mgr.process_sos_alert(new_event)

    # dispatch SMS/email notifications if notification service configured
    async def _notify(recipient: str, msg: str, notif_type: str = "sms"):
        if not NOTIFICATION_URL or not recipient:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{NOTIFICATION_URL}/notifications/",
                    json={
                        "user_id": 0,
                        "type": notif_type,
                        "message": msg,
                        "recipient": recipient,
                    }
                )
        except Exception as e:
            logger.error(f"SOS notification call failed: {e}")

    msg_self = f"SOS received at {new_event['lat']},{new_event['lng']}. Help is on the way."
    if new_event.get("phone"):
        # notify the caller by SMS
        await _notify(new_event["phone"], msg_self, "sms")
    if new_event.get("email"):
        await _notify(new_event["email"], msg_self, "email")

    if EMERGENCY_ADMIN_NUMBER:
        admin_msg = f"New SOS alert: {new_event.get('name','')} at {new_event['lat']},{new_event['lng']}"
        # assume admin contact is phone; if contains @ then treat as email
        if "@" in EMERGENCY_ADMIN_NUMBER:
            await _notify(EMERGENCY_ADMIN_NUMBER, admin_msg, "email")
        else:
            await _notify(EMERGENCY_ADMIN_NUMBER, admin_msg, "sms")

    return enriched_event


@router.get('/active', response_model=List[SOSEventResponse])
async def get_active_sos():
    ids = []
    if _redis:
        try:
            ids = list(_redis.smembers(SOS_INDEX_KEY) or [])
        except Exception:
            ids = [e['id'] for e in _local_events]
    else:
        ids = [e['id'] for e in _local_events]

    events = []
    for eid in ids:
        e = _load_event(eid)
        if e and e.get('status') == 'active':
            events.append(e)
    return events


@router.get('/all', response_model=List[SOSEventResponse])
async def get_all_sos():
    events = []
    if _redis:
        try:
            ids = list(_redis.smembers(SOS_INDEX_KEY) or [])
            for eid in ids:
                e = _load_event(eid)
                if e:
                    events.append(e)
            return events
        except Exception:
            pass
    return _local_events


@router.post('/{event_id}/resolve', response_model=SOSEventResponse)
async def resolve_sos(event_id: str):
    event = _load_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail='SOS event not found')
    event['status'] = 'resolved'
    event['resolved_at'] = datetime.utcnow().isoformat()
    _save_event(event)
    
    # Broadcast to all SOS monitors
    await manager.broadcast_sos(event)
    return event
    return event


@router.post('/{event_id}/location', response_model=SOSEventResponse)
async def send_location_update(event_id: str, lat: float, lng: float):
    event = _load_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail='SOS event not found')
    event['lat'] = lat
    event['lng'] = lng
    event['google_maps_url'] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    _save_event(event)
    await manager.broadcast(event)
    return event


@router.post('/{event_id}/end', response_model=SOSEventResponse)
async def end_trip(event_id: str):
    event = _load_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail='SOS event not found')
    event['status'] = 'trip_ended'
    _save_event(event)
    await manager.broadcast(event)
    return event
