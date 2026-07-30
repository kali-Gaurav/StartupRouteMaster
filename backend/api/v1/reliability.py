"""
Train Punctuality / Reliability Score
========================================
GET /api/v1/trains/{train_no}/reliability

Fetches live running data from rappid.in to compute
a punctuality score. Uses cached samples to build a trend.

Score logic:
  - Fetch current run from rappid.in
  - Check if any stop has delay > 0
  - Maintain a rolling window of last 7 runs in Redis
  - Score = (on_time_runs / total_sampled_runs) * 100

Fallback: if no Redis, returns current-run delay only.

Cache: 6h per train per day (don't burn rappid.in repeatedly)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date
from typing import Optional

import httpx
from fastapi import APIRouter, Path

logger = logging.getLogger("routemaster.v1.reliability")
router = APIRouter(prefix="/trains", tags=["reliability"])

RAPPID_BASE = "https://rappid.in/apis/train.php"
HISTORY_TTL = 7 * 24 * 3600   # keep 7 days of data per train
CACHE_TTL   = 6 * 3600         # recheck after 6h


def _redis():
    try:
        import redis as rl
        url = os.getenv("REDIS_URL", "")
        if url:
            return rl.from_url(url, decode_responses=True, socket_connect_timeout=3)
    except Exception:
        pass
    return None


def _parse_delay(delay_str: str) -> int:
    if not delay_str or "on time" in delay_str.lower():
        return 0
    import re
    h = re.search(r"(\d+)\s*hr", delay_str, re.I)
    m = re.search(r"(\d+)\s*min", delay_str, re.I)
    hours = int(h.group(1)) if h else 0
    mins = int(m.group(1)) if m else 0
    if not h and not m:
        any_n = re.search(r"(\d+)", delay_str)
        return int(any_n.group(1)) if any_n else 0
    return hours * 60 + mins


def _score_label(score: int) -> tuple[str, str]:
    """Return (label, color) for a punctuality score."""
    if score >= 85:
        return "Highly Punctual", "green"
    if score >= 65:
        return "Usually On Time", "yellow"
    if score >= 40:
        return "Often Delayed", "orange"
    return "Frequently Late", "red"


async def _fetch_run_data(train_no: str) -> Optional[dict]:
    """Fetch current run from rappid.in."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(RAPPID_BASE, params={"train_no": train_no})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.debug(f"rappid.in fetch failed for {train_no}: {e}")
        return None


def _analyse_run(data: dict) -> dict:
    """Analyse a single rappid.in run response."""
    stops = data.get("data", [])
    max_delay = 0
    current_delay = 0
    current_station = ""

    for stop in stops:
        d = _parse_delay(stop.get("delay", ""))
        if d > max_delay:
            max_delay = d
        if stop.get("is_current_station"):
            current_delay = d
            current_station = stop.get("station_name", "")

    on_time = max_delay == 0
    return {
        "date": str(date.today()),
        "max_delay_mins": max_delay,
        "current_delay_mins": current_delay,
        "on_time": on_time,
        "current_station": current_station,
    }


@router.get("/{train_number}/reliability")
async def get_reliability(
    train_number: str = Path(..., description="Train number e.g. 12951"),
):
    """
    Train punctuality score based on recent runs.
    Returns score 0-100, label, color badge, and run history.
    """
    train_no = train_number.strip()
    cache_key = f"reliability:{train_no}:{date.today()}"
    history_key = f"reliability:history:{train_no}"
    r = _redis()

    # Check today's cached result
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Fetch current run
    run_data = await _fetch_run_data(train_no)

    if not run_data or not run_data.get("success"):
        return {
            "train_number": train_no,
            "available": False,
            "reason": "Live data unavailable",
            "score": None,
            "label": "Unknown",
            "color": "gray",
        }

    current_run = _analyse_run(run_data)

    # Load run history from Redis
    history = []
    if r:
        try:
            raw = r.get(history_key)
            if raw:
                history = json.loads(raw)
        except Exception:
            pass

    # Append current run if not already today
    today_str = str(date.today())
    if not any(h.get("date") == today_str for h in history):
        history.append(current_run)
        history = history[-14:]  # keep last 14 runs
        if r:
            try:
                r.setex(history_key, HISTORY_TTL, json.dumps(history))
            except Exception:
                pass

    # Compute score
    if len(history) == 0:
        score = 100 if current_run["on_time"] else 50
    else:
        on_time_count = sum(1 for h in history if h.get("on_time", True))
        score = round((on_time_count / len(history)) * 100)

    label, color = _score_label(score)

    result = {
        "train_number": train_no,
        "train_name": run_data.get("train_name", train_no),
        "available": True,
        "score": score,
        "label": label,
        "color": color,
        "current_delay_mins": current_run["current_delay_mins"],
        "max_delay_mins": current_run["max_delay_mins"],
        "on_time_today": current_run["on_time"],
        "current_station": current_run["current_station"],
        "runs_sampled": len(history),
        "updated": run_data.get("updated_time", ""),
        "history": history[-7:],  # last 7 runs in response
    }

    # Cache 6h
    if r:
        try:
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result
