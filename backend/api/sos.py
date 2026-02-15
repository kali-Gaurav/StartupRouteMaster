from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from backend.services.cache_service import cache_service
from backend.api.websockets import manager
# Use the shared limiter from its source module
from backend.utils.limiter import limiter

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


@router.post('/', response_model=SOSEventResponse)
@limiter.limit("5/minute")
async def trigger_sos(request: Request, payload: SOSPayload):
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
    await manager.broadcast(new_event)
    return new_event


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
    await manager.broadcast(event)
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
