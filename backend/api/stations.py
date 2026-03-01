from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import logging
import time

from database import get_db
from database.models import Stop  # Use Stop instead of StationMaster
from services.cache_service import cache_service
from services.station_search_service import station_search_engine
from utils.limiter import limiter
from utils.metrics import STATION_SUGGEST_LATENCY_MS, STATION_SUGGEST_REQUESTS_TOTAL

router = APIRouter(prefix="/api/stations", tags=["stations"])
logger = logging.getLogger(__name__)


class SuggestionSchema(BaseModel):
    code: str
    name: str
    city: str
    state: Optional[str] = None


@router.get("/search", response_model=Dict)
@limiter.limit("120/minute")
async def legacy_station_search(request: Request, q: str = Query(..., min_length=1), limit: int = Query(10, gt=0, le=100)):
    """Unified station search endpoint - Redirected to In-Memory Engine."""
    start_time = time.time()
    try:
        # Use the high-performance in-memory engine instead of DB
        suggestions = await run_in_threadpool(station_search_engine.suggest, q, limit)
        
        results = [
            {"name": s.name, "code": s.code, "city": s.city, "state": s.state}
            for s in suggestions
        ]
        
        return {
            "success": True, 
            "stations": results, 
            "cached": True, # In-memory is effectively a hot cache
            "latency_ms": (time.time() - start_time) * 1000
        }
    except Exception as e:
        logger.error(f"Station search failed: {e}")
        raise HTTPException(status_code=500, detail="Station search failed")


@router.get("/suggest", response_model=List[SuggestionSchema])
@limiter.limit("120/minute")
async def suggest_stations(request: Request, q: str = Query(..., min_length=2), limit: int = Query(10, gt=0, le=25)):
    """Ultra-fast station autosuggest powered by In-Memory Trie Index."""

    start_time = time.time()
    status = "failure"
    try:
        suggestions = await run_in_threadpool(station_search_engine.suggest, q, limit)
        status = "success"
        return [SuggestionSchema(code=s.code, name=s.name, city=s.city, state=s.state) for s in suggestions]
    except Exception as exc:
        logger.error("Station suggest failed for '%s': %s", q, exc)
        raise HTTPException(status_code=500, detail="Station suggest failed")
    finally:
        duration_ms = (time.time() - start_time) * 1000
        STATION_SUGGEST_LATENCY_MS.labels(endpoint="/api/stations/suggest").observe(duration_ms)
        STATION_SUGGEST_REQUESTS_TOTAL.labels(endpoint="/api/stations/suggest", status=status).inc()


@router.get("/resolve", response_model=SuggestionSchema)
@limiter.limit("60/minute")
async def resolve_station(request: Request, q: str = Query(..., min_length=2)):
    """Resolve the best station for a loose query."""

    start_time = time.time()
    status = "failure"
    try:
        resolved = await run_in_threadpool(station_search_engine.resolve, q)
        if not resolved:
            raise HTTPException(status_code=404, detail="No station matched the query")
        status = "success"
        return SuggestionSchema(code=resolved.code, name=resolved.name, city=resolved.city, state=resolved.state)
    finally:
        duration_ms = (time.time() - start_time) * 1000
        STATION_SUGGEST_LATENCY_MS.labels(endpoint="/api/stations/resolve").observe(duration_ms)
        STATION_SUGGEST_REQUESTS_TOTAL.labels(endpoint="/api/stations/resolve", status=status).inc()
