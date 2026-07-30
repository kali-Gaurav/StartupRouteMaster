"""
RouteMaster v1 SOS Safety API
================================
POST /api/v1/sos/trigger  — trigger SOS alert
GET  /api/v1/sos/{event_id} — get event status
POST /api/v1/sos/{event_id}/resolve — resolve event

Sends Twilio SMS to emergency contacts if configured.
Stores events in Supabase sos_events table.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

logger = logging.getLogger("routemaster.v1.sos")
router = APIRouter(prefix="/sos", tags=["sos-v1"])

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER", "")


# ── Schemas ──────────────────────────────────────────────────────────────────

class SOSTriggerRequest(BaseModel):
    lat: float
    lng: float
    train_no: Optional[str] = ""
    passenger_name: Optional[str] = "Passenger"
    emergency_contacts: Optional[List[str]] = []  # list of phone numbers
    message: Optional[str] = ""


class SOSResolveRequest(BaseModel):
    resolution_note: Optional[str] = ""


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_session():
    try:
        from database.infrastructure.session import SessionUser
        return SessionUser()
    except Exception:
        try:
            from database.session import SessionLocal
            return SessionLocal()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


def _store_event(event_id: str, data: dict):
    from sqlalchemy import text
    session = _get_session()
    try:
        # Try to insert into sos_events table (may not exist — handle gracefully)
        session.execute(
            text("""
                INSERT INTO sos_events
                    (id, user_id, train_no, location, status, created_at)
                VALUES
                    (:id, NULL, :train_no, :location, 'active', NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": event_id,
                "train_no": data.get("train_no", ""),
                "location": json.dumps({"lat": data["lat"], "lng": data["lng"]}),
            },
        )
        session.commit()
    except Exception as e:
        session.rollback()
        # Table may not exist yet — log and continue (don't block SOS)
        logger.warning(f"Could not persist SOS event to DB: {e}")
    finally:
        session.close()


def _update_event_status(event_id: str, status: str):
    from sqlalchemy import text
    session = _get_session()
    try:
        session.execute(
            text("UPDATE sos_events SET status = :status WHERE id = :id"),
            {"status": status, "id": event_id},
        )
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Could not update SOS event status: {e}")
    finally:
        session.close()


# ── SMS helper ────────────────────────────────────────────────────────────────

def _send_sms(to_numbers: List[str], message: str):
    """Send SMS via Twilio. Silently fails if not configured."""
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
        logger.info("Twilio not configured — SOS SMS skipped. Add TWILIO_* env vars.")
        return

    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        for number in to_numbers:
            try:
                client.messages.create(
                    body=message,
                    from_=TWILIO_FROM,
                    to=number,
                )
                logger.info(f"SOS SMS sent to {number}")
            except Exception as e:
                logger.error(f"Failed to send SOS SMS to {number}: {e}")
    except ImportError:
        logger.warning("Twilio not installed. pip install twilio")
    except Exception as e:
        logger.error(f"Twilio error: {e}")


# ── In-memory event store (fallback when DB unavailable) ─────────────────────
_events_cache: dict = {}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_sos(body: SOSTriggerRequest):
    """
    Trigger an SOS alert.
    - Stores event in DB and in-memory cache
    - Sends SMS to provided emergency contacts via Twilio
    - Returns event_id and a tracking URL
    """
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    event_data = {
        "id": event_id,
        "lat": body.lat,
        "lng": body.lng,
        "train_no": body.train_no or "",
        "passenger_name": body.passenger_name or "Passenger",
        "status": "active",
        "created_at": now,
    }

    # Store in memory (always works)
    _events_cache[event_id] = event_data

    # Persist to DB (non-blocking failure)
    _store_event(event_id, event_data)

    # Build tracking URL
    base_url = os.getenv("FRONTEND_URL", "https://routemaster.vercel.app")
    tracking_url = f"{base_url}/responder?event={event_id}"

    # Send SMS
    contacts = body.emergency_contacts or []
    if contacts:
        name = body.passenger_name or "Someone"
        train_info = f" on train {body.train_no}" if body.train_no else ""
        sms_body = (
            f"🚨 SOS ALERT: {name} needs help{train_info}!\n"
            f"Location: https://maps.google.com/?q={body.lat},{body.lng}\n"
            f"Live tracking: {tracking_url}\n"
            f"Custom message: {body.message or 'Please call immediately.'}"
        )
        _send_sms(contacts, sms_body)

    logger.info(f"SOS triggered: event={event_id}, train={body.train_no}, contacts_notified={len(contacts)}")

    return {
        "success": True,
        "event_id": event_id,
        "status": "active",
        "tracking_url": tracking_url,
        "sms_sent_to": len(contacts),
        "message": f"SOS activated. {len(contacts)} contact(s) notified." if contacts else "SOS activated. No contacts provided — add emergency contacts in settings.",
        "created_at": now,
    }


@router.get("/{event_id}")
async def get_sos_event(
    event_id: str = Path(..., description="SOS event ID"),
):
    """Get SOS event status and location."""
    # Check in-memory first
    event = _events_cache.get(event_id)
    if event:
        return event

    # Check DB
    from sqlalchemy import text
    session = _get_session()
    try:
        row = session.execute(
            text("SELECT id, train_no, location, status, created_at FROM sos_events WHERE id = :id LIMIT 1"),
            {"id": event_id},
        ).fetchone()
        if row:
            loc = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or {})
            return {
                "id": row[0],
                "train_no": row[1],
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "status": row[3],
                "created_at": str(row[4]),
            }
    except Exception as e:
        logger.warning(f"SOS DB lookup failed: {e}")
    finally:
        session.close()

    raise HTTPException(status_code=404, detail="SOS event not found.")


@router.post("/{event_id}/resolve")
async def resolve_sos(
    event_id: str = Path(...),
    body: SOSResolveRequest = SOSResolveRequest(),
):
    """Mark an SOS event as resolved."""
    if event_id in _events_cache:
        _events_cache[event_id]["status"] = "resolved"

    _update_event_status(event_id, "resolved")

    return {
        "success": True,
        "event_id": event_id,
        "status": "resolved",
        "message": "SOS event marked as resolved. Stay safe.",
    }


@router.get("/")
async def list_active_sos():
    """List active SOS events (admin use)."""
    active = [e for e in _events_cache.values() if e.get("status") == "active"]
    return {"active_events": active, "count": len(active)}


@router.get("/all")
async def list_all_sos():
    """List all SOS events — active and resolved (Dashboard use)."""
    all_events = list(_events_cache.values())

    # Also try to pull from DB
    try:
        from sqlalchemy import text
        session = _get_session()
        rows = session.execute(
            text("SELECT id, train_no, location, status, created_at FROM sos_events ORDER BY created_at DESC LIMIT 50")
        ).fetchall()
        session.close()
        for row in rows:
            if row[0] not in _events_cache:
                loc = {}
                try:
                    import json as _json
                    loc = _json.loads(row[2]) if isinstance(row[2], str) else (row[2] or {})
                except Exception:
                    pass
                all_events.append({
                    "id": row[0],
                    "train_no": row[1],
                    "lat": loc.get("lat", 0),
                    "lng": loc.get("lng", 0),
                    "status": row[3],
                    "created_at": str(row[4]),
                    "passenger_name": "Passenger",
                })
    except Exception:
        pass

    return {"events": all_events, "count": len(all_events)}


@router.post("/{event_id}/telemetry")
async def update_telemetry(
    event_id: str = Path(...),
    body: dict = None,
):
    """Receive real-time telemetry from a passenger's device (battery, speed, GPS)."""
    if body is None:
        body = {}

    if event_id in _events_cache:
        _events_cache[event_id]["last_telemetry"] = {
            "lat": body.get("lat", _events_cache[event_id].get("lat")),
            "lng": body.get("lng", _events_cache[event_id].get("lng")),
            "battery": body.get("battery_level", 1.0),
            "speed": body.get("speed_kmh", 0),
            "accuracy": body.get("accuracy_m", 50),
            "updated_at": body.get("timestamp", ""),
        }
        # Update main coordinates if provided
        if body.get("lat"):
            _events_cache[event_id]["lat"] = body["lat"]
            _events_cache[event_id]["lng"] = body["lng"]

    return {"ok": True, "event_id": event_id}


@router.post("/{event_id}/location")
async def update_location(
    event_id: str = Path(...),
    body: dict = None,
):
    """Update GPS location for a live SOS event."""
    if body is None:
        body = {}

    lat = body.get("lat")
    lng = body.get("lng")

    if event_id in _events_cache and lat is not None and lng is not None:
        _events_cache[event_id]["lat"] = lat
        _events_cache[event_id]["lng"] = lng

        # Persist to DB
        try:
            from sqlalchemy import text
            import json as _json
            session = _get_session()
            session.execute(
                text("UPDATE sos_events SET location = :loc WHERE id = :id"),
                {"loc": _json.dumps({"lat": lat, "lng": lng}), "id": event_id},
            )
            session.commit()
            session.close()
        except Exception:
            pass

    return {"ok": True, "event_id": event_id, "lat": lat, "lng": lng}


@router.post("/{event_id}/end")
async def end_trip(event_id: str = Path(...)):
    """Mark a journey as safely ended (not an emergency — just trip done)."""
    if event_id in _events_cache:
        _events_cache[event_id]["status"] = "trip_ended"

    _update_event_status(event_id, "trip_ended")
    return {"ok": True, "event_id": event_id, "status": "trip_ended"}
