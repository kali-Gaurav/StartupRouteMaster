"""
RouteMaster v1 PNR Status API
================================
GET /api/v1/pnr/{pnr_number}
Checks PNR booking status via RapidAPI. Cached 5 minutes.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Path

logger = logging.getLogger("routemaster.v1.pnr")
router = APIRouter(prefix="/pnr", tags=["pnr-v1"])

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "indian-railway-irctc.p.rapidapi.com"


def _redis():
    try:
        from services.cache.multi_layer import multi_layer_cache
        r = getattr(multi_layer_cache, "redis", None)
        if r:
            return r
    except Exception:
        pass
    try:
        import redis as rl
        url = os.getenv("REDIS_URL", "")
        if url:
            return rl.from_url(url, decode_responses=True)
    except Exception:
        pass
    return None


@router.get("/{pnr_number}")
async def check_pnr(
    pnr_number: str = Path(..., min_length=10, max_length=10, description="10-digit PNR number"),
):
    """
    Check PNR booking status.
    Returns berth allocation, coach, booking status.
    Cached 5 minutes in Redis.
    """
    pnr = pnr_number.strip()
    if not pnr.isdigit() or len(pnr) != 10:
        raise HTTPException(status_code=400, detail="PNR must be exactly 10 digits.")

    cache_key = f"pnr:{pnr}"
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

    if not RAPIDAPI_KEY:
        raise HTTPException(
            status_code=503,
            detail="PNR check requires RAPIDAPI_KEY configuration. Add it to your .env file.",
        )

    try:
        import httpx
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://{RAPIDAPI_HOST}/api/pnr-status/pnr/{pnr}",
                headers=headers,
            )

            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"PNR {pnr} not found or invalid.")
            if resp.status_code == 429:
                raise HTTPException(status_code=429, detail="PNR check rate limit reached. Try again in a minute.")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"PNR service error: {resp.status_code}")

            data = resp.json()
            body = data.get("body", data.get("data", data))

            # Normalise response
            result = {
                "pnr": pnr,
                "status": body.get("pnrStatus", body.get("booking_status", "UNKNOWN")),
                "train_number": body.get("trainNumber", body.get("train_number", "")),
                "train_name": body.get("trainName", body.get("train_name", "")),
                "from_station": body.get("fromStation", body.get("boarding_station", "")),
                "to_station": body.get("toStation", body.get("destination_station", "")),
                "travel_date": body.get("dateOfJourney", body.get("journey_date", "")),
                "class": body.get("ticketClass", body.get("class_code", "")),
                "quota": body.get("quota", "GN"),
                "chart_status": body.get("chartStatus", body.get("chart_prepared", "NOT PREPARED")),
                "passengers": _parse_passengers(body),
                "cached": False,
            }

            # Cache 5 minutes
            if r:
                try:
                    r.setex(cache_key, 300, json.dumps(result))
                except Exception:
                    pass

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PNR check failed for {pnr}: {e}")
        raise HTTPException(status_code=500, detail=f"PNR check failed: {str(e)}")


def _parse_passengers(body: dict) -> list:
    """Extract passenger details from various API response formats."""
    passengers = body.get("passengerList", body.get("passengers", []))
    if not passengers:
        return []
    result = []
    for p in passengers:
        result.append({
            "number": p.get("passengerSerialNumber", p.get("number", "")),
            "booking_status": p.get("passengerBookingStatus", p.get("booking_status", "")),
            "current_status": p.get("passengerCurrentStatus", p.get("current_status", "")),
            "coach": p.get("passengerCoachId", p.get("coach", "")),
            "berth": p.get("passengerBerthNo", p.get("berth", "")),
            "berth_type": p.get("passengerBerthCode", p.get("berth_type", "")),
        })
    return result
