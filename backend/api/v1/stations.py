"""
RouteMaster v1 Stations API
============================
GET /api/v1/stations/suggest?q=delhi&limit=10
Ultra-fast station autocomplete. Uses in-memory trie if available, falls back to DB.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger("routemaster.v1.stations")
router = APIRouter(prefix="/stations", tags=["stations-v1"])


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


@router.get("/suggest")
async def suggest_stations(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query — station name, code, or city"),
    limit: int = Query(10, ge=1, le=25),
):
    """
    Station autocomplete. Tries (in order):
    1. In-memory trie index (fastest)
    2. Redis cache
    3. DB query (fallback)
    """
    q_clean = q.strip()
    if len(q_clean) < 2:
        return []

    cache_key = f"stations:suggest:{q_clean.upper()}:{limit}"
    r = _redis()

    # Redis cache check
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    results = []

    # Try in-memory trie index first (fastest — pre-loaded at startup)
    try:
        from services.station_search_service import station_search_engine
        suggestions = station_search_engine.suggest(q_clean, limit)
        results = [
            {
                "code": s.code,
                "name": s.name,
                "city": getattr(s, "city", "") or "",
                "state": getattr(s, "state", "") or "",
            }
            for s in suggestions
            if s.code and s.name
        ]
    except Exception as e:
        logger.debug(f"Trie index unavailable: {e}")

    # DB fallback
    if not results:
        try:
            from core.route_engine.data_provider import DataProvider
            dp = DataProvider()
            db_results = dp.search_stations(q_clean, limit)
            results = [
                {"code": s.code, "name": s.name, "city": s.city, "state": s.state}
                for s in db_results
                if s.code and s.name
            ]
            dp.close()
        except Exception as e:
            logger.error(f"DB station search failed: {e}")
            raise HTTPException(status_code=500, detail="Station search temporarily unavailable.")

    # Cache 24 hours
    if r and results:
        try:
            r.setex(cache_key, 86400, json.dumps(results))
        except Exception:
            pass

    return results


@router.get("/search")
async def search_stations(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=25),
):
    """Alias for /suggest — same response."""
    return await suggest_stations(request=None, q=q, limit=limit)


@router.get("/{station_code}/departures")
async def get_station_departures(
    station_code: str,
    date: str = None,
    limit: int = 50,
):
    """
    All trains departing from a station on a given date, sorted by departure time.
    Used by the Station Departures Board page.
    """
    import json as _json
    from datetime import date as _date, datetime as _dt

    code = station_code.upper().strip()
    travel_date = _date.today()
    if date:
        try:
            travel_date = _dt.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            pass

    cache_key = f"departures:{code}:{travel_date}"
    r = _redis()
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                return _json.loads(cached)
        except Exception:
            pass

    try:
        from core.route_engine.data_provider import DataProvider
        from sqlalchemy import text
        dp = DataProvider()

        # Find the stop
        stop = dp.find_stop(code)
        if not stop:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Station '{code}' not found.")

        # Get all trips that depart from this station
        rows = dp.session.execute(
            text("""
                SELECT
                    t.route_id,
                    t.trip_id,
                    st.departure_time,
                    st.stop_sequence,
                    st.departure_timestamp
                FROM stop_times st
                JOIN trips t ON t.id = st.trip_id
                WHERE st.stop_id = :stop_id
                  AND (t.is_cancelled IS NULL OR t.is_cancelled = false)
                ORDER BY st.departure_time ASC
                LIMIT :lim
            """),
            {"stop_id": stop.id, "lim": limit}
        ).fetchall()

        departures = []
        seen = set()
        for row in rows:
            route_id = row[0] or row[1] or ""
            if route_id in seen:
                continue
            seen.add(route_id)

            dep_time = str(row[2] or "").strip()
            if not dep_time or dep_time == "None":
                continue

            train_name = dp.get_train_name(route_id)
            dest = dp._get_train_dest(route_id)

            departures.append({
                "train_number": route_id,
                "train_name": train_name,
                "departure_time": dep_time[:5] if len(dep_time) >= 5 else dep_time,
                "destination": dest,
                "platform": "",  # not in GTFS — would come from live data
            })

        # Sort by departure time
        departures.sort(key=lambda d: d["departure_time"])

        result = {
            "station_code": code,
            "station_name": stop.name,
            "city": stop.city,
            "state": stop.state,
            "date": str(travel_date),
            "departures": departures[:limit],
            "total": len(departures),
        }

        dp.close()

        if r and departures:
            try:
                r.setex(cache_key, 3600, _json.dumps(result))  # 1h cache
            except Exception:
                pass

        return result
    except Exception as e:
        from fastapi import HTTPException
        if "not found" in str(e).lower():
            raise
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule/{train_number}")
async def get_train_schedule(train_number: str):
    """Full timetable for a train — all stops in sequence."""
    cache_key = f"schedule:{train_number.strip()}"
    r = _redis()
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                import json as _json
                return _json.loads(cached)
        except Exception:
            pass

    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        schedule = dp.get_train_schedule(train_number.strip())
        name = dp.get_train_name(train_number.strip())
        dp.close()

        result = {
            "train_number": train_number.strip(),
            "train_name": name,
            "stops": schedule,
            "total_stops": len(schedule),
        }

        if r and schedule:
            try:
                import json as _json
                r.setex(cache_key, 604800, _json.dumps(result))  # 7 days
            except Exception:
                pass

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{station_code}")
async def get_station(station_code: str):
    """Get a single station by code."""
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        stop = dp.find_stop(station_code.upper())
        dp.close()
        if not stop:
            raise HTTPException(status_code=404, detail=f"Station '{station_code}' not found.")
        return {
            "code": stop.code,
            "name": stop.name,
            "city": stop.city,
            "state": stop.state,
            "latitude": stop.latitude,
            "longitude": stop.longitude,
            "is_major_junction": stop.is_major_junction,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
