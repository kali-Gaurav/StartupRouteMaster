from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import logging
import time

from backend.database import get_db
from backend.database.models import Stop  # Use Stop instead of StationMaster
from backend.services.cache_service import cache_service
from backend.services.station_search_service import station_search_engine
from backend.utils.limiter import limiter
from backend.utils.metrics import STATION_SUGGEST_LATENCY_MS, STATION_SUGGEST_REQUESTS_TOTAL

router = APIRouter(prefix="/api/stations", tags=["stations"])
logger = logging.getLogger(__name__)


class SuggestionSchema(BaseModel):
    code: str
    name: str
    city: str
    state: Optional[str] = None


@router.get("/search", response_model=Dict)
async def legacy_station_search(q: str = Query(..., min_length=1), limit: int = Query(10, gt=0, le=100), db: Session = Depends(get_db)):
    """Unified station search endpoint.
    Searches across GTFS Stop table for matches.
    """
    cache_key = f"stations_search_v3:{q.lower()}:{limit}"
    
    if cache_service.is_available():
        cached_results = cache_service.get(cache_key)
        if cached_results is not None:
            return {"success": True, "stations": cached_results, "cached": True}
    
    try:
        query_lower = q.lower()
        candidates = db.query(Stop).filter(
            (Stop.name.ilike(f"%{query_lower}%")) |
            (Stop.code.ilike(f"{query_lower}%")) |
            (Stop.stop_id.ilike(f"{query_lower}%"))
        ).limit(limit).all()

        results = [
            {"name": s.name, "code": s.code or s.stop_id, "city": s.city, "state": s.state}
            for s in candidates
        ]
        
        if not results:
            from backend.database.models import StationMaster
            try:
                legacy_candidates = db.query(StationMaster).filter(
                    (StationMaster.station_name.ilike(f"%{query_lower}%")) |
                    (StationMaster.station_code.ilike(f"{query_lower}%"))
                ).limit(limit).all()
                results = [
                   {"name": s.station_name, "code": s.station_code, "city": s.city}
                   for s in legacy_candidates
                ]
            except Exception:
                pass

        if cache_service.is_available():
            cache_service.set(cache_key, results)

        return {"success": True, "stations": results, "cached": False}
    except Exception as e:
        logger.error(f"Legacy station search failed: {e}")
        raise HTTPException(status_code=500, detail="Station search failed")


@router.get("/suggest", response_model=List[SuggestionSchema])
@limiter.limit("20/second")
async def suggest_stations(request: Request, q: str = Query(..., min_length=2), limit: int = Query(10, gt=0, le=25)):
    """High performance station autosuggest powered by railway_data.db."""

    start_time = time.time()
    status = "failure"
    try:
        suggestions = await run_in_threadpool(station_search_engine.suggest, q, limit)
        status = "success"
        logger.debug("Autosuggest query '%s' returned %d candidates", q, len(suggestions))
        return [SuggestionSchema(code=s.code, name=s.name, city=s.city, state=s.state) for s in suggestions]
    except Exception as exc:
        logger.error("Station suggest failed for '%s': %s", q, exc)
        raise HTTPException(status_code=500, detail="Station suggest failed")
    finally:
        duration_ms = (time.time() - start_time) * 1000
        STATION_SUGGEST_LATENCY_MS.labels(endpoint="/api/stations/suggest").observe(duration_ms)
        STATION_SUGGEST_REQUESTS_TOTAL.labels(endpoint="/api/stations/suggest", status=status).inc()


@router.get("/resolve", response_model=SuggestionSchema)
async def resolve_station(q: str = Query(..., min_length=2)):
    """Resolve the best station for a loose query."""

    resolved = await run_in_threadpool(station_search_engine.resolve, q)
    if not resolved:
        raise HTTPException(status_code=404, detail="No station matched the query")
    return SuggestionSchema(code=resolved.code, name=resolved.name, city=resolved.city, state=resolved.state)
