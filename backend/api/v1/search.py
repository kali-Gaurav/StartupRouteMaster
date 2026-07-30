"""
RouteMaster v1 Search API
=========================
GET /api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-10
Returns all routes in the exact format the React frontend expects.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger("routemaster.v1.search")
router = APIRouter(prefix="/search", tags=["search-v1"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _time_str(t: str) -> str:
    """Normalise 'HH:MM:SS' → 'HH:MM'."""
    if not t:
        return "--:--"
    parts = str(t).split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return t


def _reliability_badge(duration_mins: int, transfers: int) -> str:
    if transfers == 0 and duration_mins < 720:
        return "green"
    if transfers <= 1:
        return "green" if duration_mins < 900 else "yellow"
    return "yellow"


def _fare_estimate(duration_mins: int, travel_class: str = "SL") -> int:
    """Rough fare estimate when real fare data is unavailable."""
    distance_km = int(duration_mins * 0.9)  # rough: ~54 km/h avg
    base_rates = {"SL": 0.36, "3A": 0.67, "2A": 1.12, "1A": 2.15, "CC": 0.71, "2S": 0.21, "3E": 0.55}
    rate = base_rates.get(travel_class, 0.36)
    return max(60, int(distance_km * rate))


async def _fetch_real_fares(train_no: str, distance_km: int = 0) -> Optional[Dict[str, Any]]:
    """
    Fetch actual IRCTC fares from erail.in via the fare API.
    Returns {classes: [...], fares: {class: {base, tatkal}}} or None on failure.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://erail.in/rail/getTrains.aspx",
                params={"TrainNo": train_no, "DataSource": "0", "Language": "0", "Cache": "true"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; RouteMaster/1.0)"},
            )
            if resp.status_code != 200:
                return None
        # Delegate parsing to fare module
        from api.v1.fare import _parse_erail_fares
        return _parse_erail_fares(resp.text)
    except Exception:
        return None


def _irctc_url(from_code: str, to_code: str, travel_date: date, train_number: str = "", travel_class: str = "SL") -> str:
    from urllib.parse import urlencode
    date_str = travel_date.strftime("%d/%m/%Y")
    class_map = {"SL": "SL", "3A": "3A", "2A": "2A", "1A": "1A", "CC": "CC", "EC": "EC"}
    irctc_class = class_map.get(travel_class, "SL")
    params: Dict[str, str] = {
        "fromStn": from_code.upper(),
        "toStn": to_code.upper(),
        "jrnyDate": date_str,
        "jrnyClass": irctc_class,
        "jrnySrc": "P",
        "returnDate": "",
        "ticketType": "E",
        "quota": "GN",
    }
    if train_number:
        params["trainNo"] = train_number
    return f"https://www.irctc.co.in/nget/train-search?{urlencode(params)}"


def _get_redis():
    try:
        from services.cache.multi_layer import multi_layer_cache
        return getattr(multi_layer_cache, "redis", None)
    except Exception:
        pass
    try:
        import os
        import redis as redis_lib
        url = os.getenv("REDIS_URL", "")
        if url:
            return redis_lib.from_url(url, decode_responses=True)
    except Exception:
        pass
    return None


async def _cache_get(redis, key: str) -> Optional[Any]:
    if not redis:
        return None
    try:
        raw = redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _cache_set(redis, key: str, value: Any, ttl: int = 300):
    if not redis:
        return
    try:
        redis.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def _build_journey(
    trip,
    from_stop,
    to_stop,
    from_code: str,
    to_code: str,
    travel_date: date,
    travel_class: str = "SL",
    num_transfers: int = 0,
    fare_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    dep = _time_str(trip.departure_time)
    arr = _time_str(trip.arrival_time)
    duration = trip.duration_minutes
    train_no = trip.route_id or trip.trip_id or ""

    # Use real fare from erail.in if available, otherwise estimate
    fare = _fare_estimate(duration, travel_class)
    available_classes: List[str] = []
    if fare_data:
        class_fare = fare_data.get("fares", {}).get(travel_class)
        if class_fare and class_fare.get("base"):
            fare = class_fare["base"]
        available_classes = fare_data.get("classes", [])

    irctc = _irctc_url(from_code, to_code, travel_date, train_no, travel_class)
    journey_id = str(uuid.uuid4())

    leg = {
        "train_number": train_no,
        "train_name": trip.train_name or train_no,
        "from_station_code": from_code,
        "to_station_code": to_code,
        "departure_time": dep,
        "arrival_time": arr,
        "duration_minutes": duration,
        "fare": fare,
        "distance": 0,
        "metadata": {},
    }

    return {
        "journey_id": journey_id,
        "num_transfers": num_transfers,
        "departure_time": dep,
        "arrival_time": arr,
        "total_duration": duration,
        "total_cost": fare,
        "total_distance": 0,
        "availability_status": "AVAILABLE",
        "reliability_badge": _reliability_badge(duration, num_transfers),
        "is_locked": False,
        "legs": [leg],
        "metadata": {
            "irctc_url": irctc,
            "train_number": train_no,
            "available_classes": available_classes,
            "fare_source": "erail" if fare_data else "estimate",
            "cached": False,
        },
    }


def _build_transfer_journey(
    transfer,
    from_code: str,
    to_code: str,
    travel_date: date,
    travel_class: str = "SL",
) -> Dict[str, Any]:
    leg1 = transfer.leg1
    leg2 = transfer.leg2
    hub = transfer.hub_stop

    fare1 = _fare_estimate(leg1.duration_minutes, travel_class)
    fare2 = _fare_estimate(leg2.duration_minutes, travel_class)
    total_fare = fare1 + fare2

    irctc = _irctc_url(from_code, to_code, travel_date, "", travel_class)

    legs = [
        {
            "train_number": leg1.route_id or leg1.trip_id,
            "train_name": leg1.train_name or leg1.route_id,
            "from_station_code": from_code,
            "to_station_code": hub.code,
            "departure_time": _time_str(leg1.departure_time),
            "arrival_time": _time_str(leg1.arrival_time),
            "duration_minutes": leg1.duration_minutes,
            "fare": fare1,
            "distance": 0,
        },
        {
            "train_number": leg2.route_id or leg2.trip_id,
            "train_name": leg2.train_name or leg2.route_id,
            "from_station_code": hub.code,
            "to_station_code": to_code,
            "departure_time": _time_str(leg2.departure_time),
            "arrival_time": _time_str(leg2.arrival_time),
            "duration_minutes": leg2.duration_minutes,
            "fare": fare2,
            "distance": 0,
        },
    ]

    return {
        "journey_id": str(uuid.uuid4()),
        "num_transfers": 1,
        "departure_time": _time_str(leg1.departure_time),
        "arrival_time": _time_str(leg2.arrival_time),
        "total_duration": transfer.total_duration_minutes,
        "total_cost": total_fare,
        "total_distance": 0,
        "availability_status": "AVAILABLE",
        "reliability_badge": _reliability_badge(transfer.total_duration_minutes, 1),
        "is_locked": False,
        "legs": legs,
        "metadata": {
            "irctc_url": irctc,
            "hub_station": hub.code,
            "hub_name": hub.name,
            "layover_minutes": transfer.layover_minutes,
            "cached": False,
        },
    }


def _runs_on_day(days_str: Optional[str], weekday: int) -> bool:
    """
    days_str: '1111111' where index 0=Mon, 6=Sun.
    Returns True if the train runs on the given weekday.
    If days_str is None/empty, assume runs every day.
    """
    if not days_str or len(days_str) < 7:
        return True  # Unknown — assume runs
    return days_str[weekday] == "1"


def _build_two_transfer_journey(
    route_pair: tuple,  # (leg1_transfer, leg2_transfer)
    from_code: str,
    to_code: str,
    travel_date: date,
    travel_class: str = "SL",
) -> Dict[str, Any]:
    """Build a 2-transfer journey from two TransferRoute objects."""
    tr1, tr2 = route_pair
    # tr1: from_code → hub1, tr2: hub1 → to_code (via hub2)
    leg1 = tr1.leg1
    leg_mid = tr1.leg2
    leg2 = tr2.leg2

    fare1 = _fare_estimate(leg1.duration_minutes, travel_class)
    fare_mid = _fare_estimate(leg_mid.duration_minutes, travel_class)
    fare2 = _fare_estimate(leg2.duration_minutes, travel_class)
    total_fare = fare1 + fare_mid + fare2

    irctc = _irctc_url(from_code, to_code, travel_date, "", travel_class)

    legs = [
        {
            "train_number": leg1.route_id or leg1.trip_id,
            "train_name": leg1.train_name or leg1.route_id,
            "from_station_code": from_code,
            "to_station_code": tr1.hub_stop.code,
            "departure_time": _time_str(leg1.departure_time),
            "arrival_time": _time_str(leg1.arrival_time),
            "duration_minutes": leg1.duration_minutes,
            "fare": fare1,
            "distance": 0,
        },
        {
            "train_number": leg_mid.route_id or leg_mid.trip_id,
            "train_name": leg_mid.train_name or leg_mid.route_id,
            "from_station_code": tr1.hub_stop.code,
            "to_station_code": tr2.hub_stop.code,
            "departure_time": _time_str(leg_mid.departure_time),
            "arrival_time": _time_str(leg_mid.arrival_time),
            "duration_minutes": leg_mid.duration_minutes,
            "fare": fare_mid,
            "distance": 0,
        },
        {
            "train_number": leg2.route_id or leg2.trip_id,
            "train_name": leg2.train_name or leg2.route_id,
            "from_station_code": tr2.hub_stop.code,
            "to_station_code": to_code,
            "departure_time": _time_str(leg2.departure_time),
            "arrival_time": _time_str(leg2.arrival_time),
            "duration_minutes": leg2.duration_minutes,
            "fare": fare2,
            "distance": 0,
        },
    ]

    total_dur = tr1.total_duration_minutes + tr2.total_duration_minutes
    return {
        "journey_id": str(uuid.uuid4()),
        "num_transfers": 2,
        "departure_time": _time_str(leg1.departure_time),
        "arrival_time": _time_str(leg2.arrival_time),
        "total_duration": total_dur,
        "total_cost": total_fare,
        "total_distance": 0,
        "availability_status": "AVAILABLE",
        "reliability_badge": "yellow",
        "is_locked": False,
        "legs": legs,
        "metadata": {
            "irctc_url": irctc,
            "hub1": tr1.hub_stop.code,
            "hub2": tr2.hub_stop.code,
            "cached": False,
        },
    }


def _group_journeys(journeys: List[Dict]) -> Dict[str, List[Dict]]:
    direct = [j for j in journeys if j["num_transfers"] == 0]
    one_tr = [j for j in journeys if j["num_transfers"] == 1]
    two_tr = [j for j in journeys if j["num_transfers"] == 2]

    sorted_all = sorted(journeys, key=lambda j: j["total_duration"])

    return {
        "top_3_confirmed_fastest": sorted_all[:3],
        "top_10_fastest_total": sorted_all[:10],
        "top_5_optimal": sorted_all[:5],
        "direct": direct,
        "one_transfer": one_tr,
        "two_transfer": two_tr,
        "three_plus_transfer": [],
        "alternative_sorted": sorted_all,
    }


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/routes")
async def search_routes(
    request: Request,
    source: str = Query(..., min_length=2, max_length=10, description="Origin station code e.g. NDLS"),
    destination: str = Query(..., min_length=2, max_length=10, description="Destination station code e.g. BCT"),
    date: Optional[str] = Query(None, description="Travel date YYYY-MM-DD, default today"),
    persona: str = Query("BUSINESS", description="Ranking persona"),
    limit: int = Query(20, ge=1, le=50),
    travel_class: str = Query("SL", description="Class: SL, 3A, 2A, 1A, CC"),
):
    start = time.perf_counter()
    src = source.upper().strip()
    dst = destination.upper().strip()

    if src == dst:
        raise HTTPException(status_code=400, detail="Source and destination cannot be the same.")

    # Parse date
    try:
        travel_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
    except ValueError:
        travel_date = datetime.now().date()

    # Cache key
    cache_key = f"search:v1:{src}:{dst}:{travel_date}:{travel_class}"
    redis = _get_redis()
    cached = await _cache_get(redis, cache_key)
    if cached:
        cached["metadata"] = {**cached.get("metadata", {}), "cached": True, "latency_ms": round((time.perf_counter() - start) * 1000)}
        return cached

    # Get data provider
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
    except Exception as e:
        logger.error(f"DataProvider init failed: {e}")
        raise HTTPException(status_code=503, detail="Route engine unavailable. Please try again.")

    # Find stops
    from_stop = dp.find_stop(src)
    to_stop = dp.find_stop(dst)

    if not from_stop:
        raise HTTPException(status_code=404, detail=f"Station '{src}' not found. Try the full station code (e.g. NDLS, BCT, MAS).")
    if not to_stop:
        raise HTTPException(status_code=404, detail=f"Station '{dst}' not found. Try the full station code (e.g. NDLS, BCT, MAS).")

    # Search direct trains
    direct_trains = dp.find_direct_trains(src, dst, travel_date, limit=min(limit, 15))

    # Filter by day-of-week using trains_master.days_of_run ("1111111" = Mon-Sun)
    day_of_week = travel_date.weekday()  # 0=Mon, 6=Sun
    filtered_direct = []
    for train in direct_trains:
        days = dp.get_train_days(train.route_id)
        if _runs_on_day(days, day_of_week):
            filtered_direct.append(train)
    if filtered_direct:
        direct_trains = filtered_direct
    # If day filter removed everything, keep original (days_of_run may not be populated)

    # Search 1-transfer routes
    transfer_routes = []
    try:
        transfer_routes = dp.find_hub_trains(src, dst, limit_per_leg=8)
    except Exception as e:
        logger.warning(f"Hub search failed: {e}")

    # Search 2-transfer routes if still thin
    two_transfer_routes = []
    if len(direct_trains) + len(transfer_routes) < 3:
        try:
            two_transfer_routes = dp.find_two_transfer_routes(src, dst, limit=3)
        except Exception as e:
            logger.debug(f"2-transfer search failed: {e}")

    # Fetch real fares from erail.in for the first train found (reused for all — same route)
    fare_data: Optional[Dict] = None
    if direct_trains:
        first_train_no = direct_trains[0].route_id or direct_trains[0].trip_id or ""
        if first_train_no:
            try:
                fare_data = await _fetch_real_fares(first_train_no)
                if fare_data:
                    logger.info(f"Real fares loaded for {first_train_no}: classes={fare_data.get('classes')}")
            except Exception as e:
                logger.debug(f"Fare fetch failed for {first_train_no}: {e}")

    # Build journeys
    journeys: List[Dict] = []
    for train in direct_trains[:limit]:
        # Try per-train fare data; fall back to route-level data
        train_fare_data = fare_data
        if not train_fare_data or (train.route_id and train.route_id != (direct_trains[0].route_id if direct_trains else "")):
            train_fare_data = fare_data  # reuse — same route, similar fares
        try:
            j = _build_journey(train, from_stop, to_stop, src, dst, travel_date, travel_class, 0, train_fare_data)
            journeys.append(j)
        except Exception as e:
            logger.warning(f"Failed to build journey for {train.route_id}: {e}")

    for tr in transfer_routes[:5]:
        try:
            j = _build_transfer_journey(tr, src, dst, travel_date, travel_class)
            journeys.append(j)
        except Exception as e:
            logger.warning(f"Failed to build transfer journey: {e}")

    for tr in two_transfer_routes[:3]:
        try:
            j = _build_two_transfer_journey(tr, src, dst, travel_date, travel_class)
            journeys.append(j)
        except Exception as e:
            logger.warning(f"Failed to build 2-transfer journey: {e}")

    # Sort by duration
    journeys.sort(key=lambda j: j["total_duration"])

    # Station map
    stations_map = {
        src: {"code": src, "name": from_stop.name, "city": from_stop.city, "state": from_stop.state},
        dst: {"code": dst, "name": to_stop.name, "city": to_stop.city, "state": to_stop.state},
    }

    # Build response
    grouped = _group_journeys(journeys)
    latency = round((time.perf_counter() - start) * 1000)

    response = {
        "status": "success" if journeys else "no_results",
        "source": src,
        "destination": dst,
        "stations": stations_map,
        "data": {
            "journeys": journeys,
            "grouped_journeys": grouped,
            "pagination": {
                "total_results": len(journeys),
                "current_page": 1,
                "limit": limit,
                "has_next": False,
                "total_pages": 1,
            },
        },
        "journey_message": (
            f"Found {len(journeys)} route(s) from {from_stop.name} to {to_stop.name}."
            if journeys else
            f"No direct routes found from {from_stop.name} to {to_stop.name}. Try nearby stations."
        ),
        "metadata": {
            "engine": "routemaster-v1",
            "latency_ms": latency,
            "cached": False,
            "direct_count": len([j for j in journeys if j["num_transfers"] == 0]),
            "transfer_count": len([j for j in journeys if j["num_transfers"] > 0]),
            "fare_source": "erail" if fare_data else "estimate",
            "available_classes": fare_data.get("classes", []) if fare_data else [],
        },
    }

    # Cache 5 minutes
    await _cache_set(redis, cache_key, response, ttl=300)

    dp.close()
    return response


@router.get("/stations/search")
async def search_stations_inline(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=25),
):
    """Inline station search — same as /api/v1/stations/suggest."""
    try:
        from services.station_search_service import station_search_engine
        results = station_search_engine.suggest(q, limit)
        return [{"code": s.code, "name": s.name, "city": s.city, "state": getattr(s, "state", "")} for s in results]
    except Exception:
        pass
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        results = dp.search_stations(q, limit)
        dp.close()
        return [{"code": s.code, "name": s.name, "city": s.city, "state": s.state} for s in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Station search failed: {e}")
