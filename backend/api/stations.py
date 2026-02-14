

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict
from sqlalchemy.orm import Session
import logging

from backend.database import get_db
from backend.models import StationMaster
from backend.services.cache_service import cache_service

router = APIRouter(prefix="/api/stations", tags=["stations"])
logger = logging.getLogger(__name__)


@router.get("/search", response_model=Dict)
async def legacy_station_search(q: str = Query(..., min_length=1), limit: int = Query(10, gt=0, le=100), db: Session = Depends(get_db)):
    """Backward-compatible station search endpoint used by older clients/tests.

    Returns an envelope { success: bool, stations: [...], cached: bool }
    """
    cache_key = f"stations_autocomplete_legacy:{q.lower()}:{limit}"
    cached = False

    if cache_service.is_available():
        cached_results = cache_service.get(cache_key)
        if cached_results is not None:
            return {"success": True, "stations": cached_results, "cached": True}

    # Query StationMaster (legacy data source used by frontend)
    try:
        query_lower = q.lower()
        candidates = db.query(StationMaster).filter(
            (StationMaster.station_name.ilike(f"%{query_lower}%")) |
            (StationMaster.station_code.ilike(f"{query_lower}%"))
        ).limit(limit).all()

        results = [
            {"name": s.station_name, "code": s.station_code, "city": s.city}
            for s in candidates
        ]

        # Store into cache (fallback cache is available in cache_service)
        cache_service.set(cache_key, results)

        return {"success": True, "stations": results, "cached": False}
    except Exception as e:
        logger.error(f"Legacy station search failed: {e}")
        raise HTTPException(status_code=500, detail="Station search failed")
