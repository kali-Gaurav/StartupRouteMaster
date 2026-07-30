"""
RouteMaster Fare Alerts
========================
Users set a fare threshold for a route.
When fares drop below their threshold, we notify them via Telegram.

Endpoints:
  POST /api/v1/alerts/fare        — set alert
  GET  /api/v1/alerts/mine        — list user's alerts
  DELETE /api/v1/alerts/{id}      — cancel alert
  POST /api/v1/alerts/check       — admin: check + fire notifications (run daily)

Table: fare_alerts
  id, user_id (Firebase UID), telegram_chat_id (optional),
  from_code, to_code, travel_date, travel_class,
  threshold_inr, last_fare_inr, notified, created_at

Business logic:
  - User sets alert: "Notify me if SL fare NDLS→BCT on 20 June < ₹800"
  - Daily cron hits /api/v1/alerts/check
  - We fetch fare from erail.in
  - If fare <= threshold and not yet notified → send Telegram msg
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("routemaster.v1.alerts")
router = APIRouter(prefix="/alerts", tags=["alerts"])
bearer = HTTPBearer(auto_error=False)

# In-memory store (falls back when DB unavailable)
_alerts: dict = {}


# ── DB helpers ────────────────────────────────────────────────────────────────

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


def _ensure_table():
    """Create fare_alerts table if missing."""
    from sqlalchemy import text
    try:
        session = _get_session()
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS fare_alerts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                telegram_chat_id TEXT,
                from_code TEXT NOT NULL,
                to_code TEXT NOT NULL,
                travel_date TEXT NOT NULL,
                travel_class TEXT DEFAULT 'SL',
                threshold_inr INTEGER NOT NULL,
                last_fare_inr INTEGER,
                notified BOOLEAN DEFAULT false,
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        session.commit()
        session.close()
    except Exception:
        pass  # Table may already exist


# ── Schemas ───────────────────────────────────────────────────────────────────

class FareAlertRequest(BaseModel):
    from_code: str
    to_code: str
    travel_date: str           # YYYY-MM-DD
    travel_class: str = "SL"
    threshold_inr: int         # Alert when fare <= this
    telegram_chat_id: Optional[str] = None
    user_id: Optional[str] = None  # Firebase UID


# ── Fare fetch helper ─────────────────────────────────────────────────────────

async def _get_current_fare(train_no: str, travel_class: str) -> Optional[int]:
    """Fetch current fare from erail.in."""
    try:
        import httpx
        from api.v1.fare import _parse_erail_fares, ERAIL_BASE
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                ERAIL_BASE,
                params={"TrainNo": train_no, "DataSource": "0", "Language": "0", "Cache": "true"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; RouteMaster/1.0)"},
            )
        if resp.status_code == 200:
            parsed = _parse_erail_fares(resp.text)
            if parsed:
                return parsed.get("fares", {}).get(travel_class, {}).get("base")
    except Exception:
        pass
    return None


async def _send_alert_notification(alert: dict, current_fare: int):
    """Send fare alert via Telegram."""
    chat_id = alert.get("telegram_chat_id")
    if not chat_id:
        return
    try:
        from api.v1.telegram import send_message
        irctc_url = (
            f"https://www.irctc.co.in/nget/train-search?"
            f"fromStn={alert['from_code']}&toStn={alert['to_code']}"
            f"&jrnyDate={alert['travel_date'].replace('-', '/')}&jrnyClass={alert['travel_class']}"
            f"&jrnySrc=P&ticketType=E"
        )
        text = (
            f"🔔 <b>Fare Alert!</b>\n\n"
            f"🚂 <b>{alert['from_code']} → {alert['to_code']}</b>\n"
            f"📅 {alert['travel_date']} · Class: {alert['travel_class']}\n"
            f"💰 Current fare: <b>₹{current_fare}</b> (your alert: ₹{alert['threshold_inr']})\n\n"
            f"🎟️ <a href='{irctc_url}'>Book now on IRCTC</a>\n"
            f"⚡ Fares change fast — book soon!"
        )
        await send_message(int(chat_id), text)
        logger.info(f"Fare alert sent for alert {alert['id']} to chat {chat_id}")
    except Exception as e:
        logger.warning(f"Failed to send alert notification: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/fare", status_code=201)
async def set_fare_alert(
    body: FareAlertRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Set a fare alert. Notified via Telegram when fare drops below threshold."""
    _ensure_table()

    user_id = body.user_id or "anonymous"
    if credentials:
        # Try to decode JWT user_id
        try:
            from api.v1.auth import _decode_token
            payload = _decode_token(credentials.credentials)
            if payload:
                user_id = payload.get("sub", user_id)
        except Exception:
            pass

    alert_id = str(uuid.uuid4())
    alert = {
        "id": alert_id,
        "user_id": user_id,
        "telegram_chat_id": body.telegram_chat_id,
        "from_code": body.from_code.upper(),
        "to_code": body.to_code.upper(),
        "travel_date": body.travel_date,
        "travel_class": body.travel_class,
        "threshold_inr": body.threshold_inr,
        "last_fare_inr": None,
        "notified": False,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _alerts[alert_id] = alert

    try:
        from sqlalchemy import text
        session = _get_session()
        session.execute(text("""
            INSERT INTO fare_alerts
                (id, user_id, telegram_chat_id, from_code, to_code,
                 travel_date, travel_class, threshold_inr, notified, active)
            VALUES
                (:id, :uid, :tg, :from, :to, :date, :class, :thresh, false, true)
        """), {
            "id": alert_id, "uid": user_id, "tg": body.telegram_chat_id,
            "from": body.from_code.upper(), "to": body.to_code.upper(),
            "date": body.travel_date, "class": body.travel_class,
            "thresh": body.threshold_inr,
        })
        session.commit()
        session.close()
    except Exception:
        pass  # In-memory fallback is enough

    return {
        "id": alert_id,
        "message": f"Alert set! We'll notify you when {body.travel_class} fare for {body.from_code}→{body.to_code} on {body.travel_date} drops below ₹{body.threshold_inr}.",
        "telegram_connected": bool(body.telegram_chat_id),
    }


@router.get("/mine")
async def get_my_alerts(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Get all active alerts for the current user."""
    user_id = None
    if credentials:
        try:
            from api.v1.auth import _decode_token
            payload = _decode_token(credentials.credentials)
            if payload:
                user_id = payload.get("sub")
        except Exception:
            pass

    alerts = [a for a in _alerts.values() if a.get("active") and (not user_id or a.get("user_id") == user_id)]
    return {"alerts": alerts, "count": len(alerts)}


@router.delete("/{alert_id}")
async def cancel_alert(alert_id: str):
    """Cancel a fare alert."""
    if alert_id in _alerts:
        _alerts[alert_id]["active"] = False

    try:
        from sqlalchemy import text
        session = _get_session()
        session.execute(text("UPDATE fare_alerts SET active=false WHERE id=:id"), {"id": alert_id})
        session.commit()
        session.close()
    except Exception:
        pass

    return {"cancelled": True, "id": alert_id}


@router.get("/run-daily")
async def run_daily_cron():
    """
    GET endpoint for cron jobs (Render cron / GitHub Actions).
    Calls check_and_fire_alerts internally.
    Also sends a summary to admin Telegram chat if configured.
    """
    result = await check_and_fire_alerts()

    # Optionally notify admin via Telegram
    admin_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if admin_chat and result.get("checked", 0) > 0:
        try:
            from api.v1.telegram import send_message
            summary = (
                f"📊 <b>Route Master Daily Report</b>\n"
                f"🔔 Fare alerts checked: {result['checked']}\n"
                f"✅ Notifications sent: {result['notified']}\n"
                f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            )
            await send_message(int(admin_chat), summary)
        except Exception:
            pass

    return {**result, "ran_at": datetime.now(timezone.utc).isoformat()}


@router.post("/check")
async def check_and_fire_alerts():
    """
    Check all active alerts and fire notifications.
    Call this daily via a cron or scheduled task.
    Returns list of alerts checked and which were notified.
    """
    active = [a for a in _alerts.values() if a.get("active") and not a.get("notified")]
    notified = []
    checked = 0

    # Also load from DB
    try:
        from sqlalchemy import text
        session = _get_session()
        rows = session.execute(text("""
            SELECT id, user_id, telegram_chat_id, from_code, to_code,
                   travel_date, travel_class, threshold_inr
            FROM fare_alerts WHERE active=true AND notified=false
        """)).fetchall()
        session.close()
        for row in rows:
            a = {
                "id": row[0], "user_id": row[1], "telegram_chat_id": row[2],
                "from_code": row[3], "to_code": row[4], "travel_date": str(row[5]),
                "travel_class": row[6], "threshold_inr": row[7],
            }
            if a["id"] not in _alerts:
                active.append(a)
    except Exception:
        pass

    for alert in active[:50]:  # max 50 checks per run
        checked += 1
        try:
            # Find a train for this route
            from core.route_engine.data_provider import DataProvider
            dp = DataProvider()
            trains = dp.find_direct_trains(alert["from_code"], alert["to_code"], limit=1)
            dp.close()

            if not trains:
                continue

            first_train = trains[0].route_id or trains[0].trip_id
            fare = await _get_current_fare(first_train, alert["travel_class"])

            if fare is None:
                continue

            if fare <= alert["threshold_inr"]:
                await _send_alert_notification(alert, fare)
                # Mark notified
                if alert["id"] in _alerts:
                    _alerts[alert["id"]]["notified"] = True
                    _alerts[alert["id"]]["last_fare_inr"] = fare
                try:
                    from sqlalchemy import text
                    session = _get_session()
                    session.execute(
                        text("UPDATE fare_alerts SET notified=true, last_fare_inr=:fare WHERE id=:id"),
                        {"fare": fare, "id": alert["id"]}
                    )
                    session.commit()
                    session.close()
                except Exception:
                    pass
                notified.append({"id": alert["id"], "fare": fare, "threshold": alert["threshold_inr"]})
        except Exception as e:
            logger.debug(f"Alert check failed for {alert.get('id')}: {e}")

    return {
        "checked": checked,
        "notified": len(notified),
        "fired": notified,
    }
