"""
RouteMaster v1 Live Train Status API — powered by rappid.in (free, unlimited)
==============================================================================
GET /api/v1/live/train/{train_number}

Data source: https://rappid.in/apis/train.php?train_no={train_no}
- Current station, next station, delay, full route with platform info
- Free + unlimited — no quota tracking needed
- Cache 60s in Redis to avoid hammering on repeated requests
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Path, Query

logger = logging.getLogger("routemaster.v1.live")
router = APIRouter(prefix="/live", tags=["live-v1"])

RAPPID_BASE = "https://rappid.in/apis/train.php"
CACHE_TTL = 60  # seconds — short TTL since this is live status


# ── Redis helper ─────────────────────────────────────────────────────────────

def _redis():
    try:
        import redis as rl
        url = os.getenv("REDIS_URL", "")
        if url:
            return rl.from_url(url, decode_responses=True, socket_connect_timeout=3)
    except Exception:
        pass
    return None


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_timing(raw: str):
    """
    rappid.in concatenates departure+arrival times without separator.
    Format: 'HH:MMhh:mm'  e.g. '17:0017:00' → dep='17:00', arr='17:00'
    Special values: 'Source', 'Destination' → returned as-is.
    """
    if not raw:
        return "--:--", "--:--"
    if raw in ("Source", "Destination"):
        return raw, raw
    # 10-char format: first 5 = departure, last 5 = arrival
    if len(raw) >= 10:
        return raw[:5], raw[5:10]
    # 5-char: single time
    if ":" in raw:
        return raw, raw
    return raw, raw


def _parse_delay_minutes(delay_str: str) -> int:
    """'On Time' → 0, '15 min late' → 15, '2 hrs 5 min late' → 125."""
    if not delay_str or "on time" in delay_str.lower():
        return 0
    hours = 0
    mins = 0
    h_match = re.search(r"(\d+)\s*hr", delay_str, re.I)
    m_match = re.search(r"(\d+)\s*min", delay_str, re.I)
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        mins = int(m_match.group(1))
    if not h_match and not m_match:
        # fallback: just grab any number
        any_num = re.search(r"(\d+)", delay_str)
        return int(any_num.group(1)) if any_num else 0
    return hours * 60 + mins


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.get("/train/{train_number}")
async def get_live_status(
    train_number: str = Path(..., description="Train number e.g. 12951"),
):
    """
    Live train running status.
    Returns current station, next station, delay, full route with platform info.
    Powered by rappid.in — free and unlimited.
    """
    train_no = train_number.strip()
    cache_key = f"live:rappid:{train_no}"
    r = _redis()

    # Cache hit
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                result = json.loads(cached)
                result["cached"] = True
                return result
        except Exception:
            pass

    # Fetch from rappid.in
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(RAPPID_BASE, params={"train_no": train_no})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"available": False, "train_number": train_no, "reason": "timeout", "cached": False}
    except Exception as e:
        logger.warning(f"rappid.in failed for train {train_no}: {e}")
        return {"available": False, "train_number": train_no, "reason": str(e), "cached": False}

    if not data.get("success") or not data.get("data"):
        return {"available": False, "train_number": train_no, "reason": "no_data", "cached": False}

    stops: List[Dict] = data["data"]

    # Find current station (one will have is_current_station=True when train is running)
    current_idx: Optional[int] = None
    for i, stop in enumerate(stops):
        if stop.get("is_current_station"):
            current_idx = i
            break

    current_station_name = ""
    next_station_name = ""
    overall_delay = 0

    if current_idx is not None:
        current_station_name = stops[current_idx].get("station_name", "")
        overall_delay = _parse_delay_minutes(stops[current_idx].get("delay", ""))
        if current_idx + 1 < len(stops):
            next_station_name = stops[current_idx + 1].get("station_name", "")
    else:
        # Train not currently running or data is from schedule
        # Use last known delay from any stop
        for stop in reversed(stops):
            d = stop.get("delay", "")
            if d and "on time" not in d.lower() and d != "":
                overall_delay = _parse_delay_minutes(d)
                break

    # Build full route list
    route: List[Dict] = []
    for i, s in enumerate(stops):
        dep_time, arr_time = _parse_timing(s.get("timing", ""))
        delay_mins = _parse_delay_minutes(s.get("delay", ""))
        route.append({
            "station_name": s.get("station_name", ""),
            "distance": s.get("distance", ""),
            "departure": dep_time,
            "arrival": arr_time,
            "delay": s.get("delay", "On Time"),
            "delay_minutes": delay_mins,
            "platform": s.get("platform", ""),
            "halt": s.get("halt", ""),
            "is_current": s.get("is_current_station", False),
        })

    result: Dict[str, Any] = {
        "available": True,
        "train_number": train_no,
        "train_name": data.get("train_name", train_no),
        "updated": data.get("updated_time", ""),
        "delay_minutes": overall_delay,
        "current_station": current_station_name,
        "next_station": next_station_name,
        "is_running": current_idx is not None,
        "on_time": overall_delay == 0,
        "status_label": "On Time" if overall_delay == 0 else f"{overall_delay} min late",
        "badge_color": (
            "green" if overall_delay == 0
            else "yellow" if overall_delay <= 30
            else "red"
        ),
        "route": route,
        "total_stops": len(stops),
        "cached": False,
    }

    # Cache result
    if r:
        try:
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result


@router.get("/quota")
async def quota_status():
    """rappid.in is free + unlimited — no quota to track."""
    return {
        "source": "rappid.in",
        "unlimited": True,
        "quota_tracking": False,
        "message": "Live status is powered by rappid.in (free, no quota limits).",
    }
