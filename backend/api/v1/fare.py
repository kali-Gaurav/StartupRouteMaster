"""
RouteMaster v1 Fare & Class API — powered by erail.in (free)
=============================================================
GET /api/v1/fare/{train_no}?from=MMCT&to=NDLS&distance_km=1384

Returns actual IRCTC fares per class and list of available classes.
Falls back to rough estimates if erail.in data is unavailable.

Data source: https://erail.in/rail/getTrains.aspx?TrainNo={no}&DataSource=0&Language=0&Cache=true
- Parses pipe-delimited format: train type, distance, fares per class
- Class order in erail data: 1A, 2A, 3A, FC, CC, SL, 2S, 3E, EC, VC, GN
- Fares per class are comma-separated: base_fare, tatkal_fare, ..., premium_tatkal_fare
- Cache 24h (fares don't change daily)
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional, Any

import httpx
from fastapi import APIRouter, Query as QueryParam, Path

logger = logging.getLogger("routemaster.v1.fare")
router = APIRouter(prefix="/fare", tags=["fare-v1"])

ERAIL_BASE = "https://erail.in/rail/getTrains.aspx"
CACHE_TTL = 86400  # 24 hours — fares are stable

# Class slot order as used by erail.in fare data
ERAIL_CLASS_ORDER = ["1A", "2A", "3A", "FC", "CC", "SL", "2S", "3E", "EC", "VC", "GN"]

# Rough fallback fare rates per km (₹/km) when erail.in is unavailable
FALLBACK_RATES = {
    "SL": 0.36, "3A": 0.67, "2A": 1.12, "1A": 2.15,
    "CC": 0.71, "2S": 0.21, "FC": 1.80, "3E": 0.55,
    "EC": 1.40, "GN": 0.15,
}


# ── Redis ─────────────────────────────────────────────────────────────────────

def _redis():
    try:
        import redis as rl
        url = os.getenv("REDIS_URL", "")
        if url:
            return rl.from_url(url, decode_responses=True, socket_connect_timeout=3)
    except Exception:
        pass
    return None


# ── erail.in parser ───────────────────────────────────────────────────────────

def _parse_erail_fares(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse erail.in getTrains.aspx pipe-delimited response.
    Returns dict with classes, fares, distance, train_type.
    Returns None if parsing fails.
    """
    try:
        # Data block is everything after '^'
        if "^" not in raw_text:
            return None
        block = raw_text.split("^", 1)[1]

        # Split on '~'
        parts = block.split("~")
        if len(parts) < 30:
            return None

        # Field positions (approximate — robust to minor shifts)
        train_no = parts[0].strip()
        train_name = parts[1].strip() if len(parts) > 1 else ""
        train_type = ""
        fare_str = ""
        distance_km = 0

        # Find fare data — it looks like "RAJDHANI:1384:5335,..." or "MAIL:800:..."
        for p in parts:
            if re.match(r"[A-Z]+:\d+:", p.strip()):
                fare_str = p.strip()
                break

        if not fare_str:
            return None

        # Parse fare string: TrainType:distance_km:class0_fares:class1_fares:...
        fare_parts = fare_str.split(":")
        if len(fare_parts) < 3:
            return None

        train_type = fare_parts[0]
        try:
            distance_km = int(fare_parts[1])
        except ValueError:
            distance_km = 0

        # Parse fares per class
        fares: Dict[str, Dict] = {}
        classes_available: List[str] = []

        for i, class_code in enumerate(ERAIL_CLASS_ORDER):
            slot_idx = i + 2  # offset by 2 (TrainType, distance)
            if slot_idx >= len(fare_parts):
                break
            slot = fare_parts[slot_idx].strip()
            if not slot or slot == "":
                continue

            # Slot format: "base_fare,tatkal_fare,?,?,?,premium_tatkal_fare"
            values = [v.strip() for v in slot.split(",")]
            if not values or not values[0]:
                continue

            try:
                base = int(values[0])
            except ValueError:
                continue

            if base == 0:
                continue  # class not available on this train

            tatkal = 0
            premium_tatkal = 0
            try:
                tatkal = int(values[1]) if len(values) > 1 and values[1] else 0
            except ValueError:
                pass
            try:
                premium_tatkal = int(values[5]) if len(values) > 5 and values[5] else 0
            except ValueError:
                pass

            fares[class_code] = {
                "base": base,
                "tatkal": tatkal,
                "premium_tatkal": premium_tatkal,
            }
            classes_available.append(class_code)

        if not fares:
            return None

        return {
            "train_no": train_no,
            "train_name": train_name,
            "train_type": train_type,
            "distance_km": distance_km,
            "classes": classes_available,
            "fares": fares,
            "source": "erail",
        }

    except Exception as e:
        logger.debug(f"erail fare parse failed: {e}")
        return None


def _fallback_fares(distance_km: int, train_type: str = "") -> Dict[str, Any]:
    """Rough fare estimates when erail.in is unavailable."""
    km = max(distance_km, 50)

    # Infer likely classes from train type
    t = train_type.upper()
    if "RAJDHANI" in t or "DURONTO" in t or "TEJAS" in t:
        class_list = ["1A", "2A", "3A"]
    elif "SHATABDI" in t or "JAN SHATABDI" in t:
        class_list = ["1A", "CC"]
    elif "GARIB RATH" in t:
        class_list = ["3A"]
    else:
        class_list = ["SL", "3A", "2A", "1A", "2S"]

    fares: Dict[str, Dict] = {}
    for c in class_list:
        rate = FALLBACK_RATES.get(c, 0.35)
        base = max(50, int(km * rate))
        fares[c] = {
            "base": base,
            "tatkal": int(base * 0.30),
            "premium_tatkal": int(base * 0.40),
        }

    return {
        "train_no": "",
        "train_name": "",
        "train_type": train_type,
        "distance_km": distance_km,
        "classes": class_list,
        "fares": fares,
        "source": "estimate",
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/{train_number}")
async def get_fare(
    train_number: str = Path(..., description="Train number e.g. 12951"),
    distance_km: int = QueryParam(0, ge=0, description="Journey distance in km (for fallback estimates)"),
):
    """
    Get actual IRCTC fares per class for a train.

    Returns:
    - classes: list of available classes e.g. ["1A", "2A", "3A"]
    - fares: per-class base, tatkal, and premium tatkal fares
    - source: 'erail' (real data) or 'estimate' (fallback)
    """
    train_no = train_number.strip()
    cache_key = f"fare:{train_no}"
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

    # Fetch from erail.in
    parsed = None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                ERAIL_BASE,
                params={"TrainNo": train_no, "DataSource": "0", "Language": "0", "Cache": "true"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; RouteMaster/1.0)"},
            )
            if resp.status_code == 200:
                parsed = _parse_erail_fares(resp.text)
    except Exception as e:
        logger.debug(f"erail.in request failed for {train_no}: {e}")

    if parsed:
        result = {**parsed, "cached": False}
    else:
        result = {**_fallback_fares(distance_km), "train_no": train_no, "cached": False}

    # Cache 24h
    if r:
        try:
            r.setex(cache_key, CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result
