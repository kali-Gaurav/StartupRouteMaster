

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict
from sqlalchemy.orm import Session
import logging

from backend.database import get_db
from backend.database.models import Stop # Use Stop instead of StationMaster
from backend.services.cache_service import cache_service

router = APIRouter(prefix="/api/stations", tags=["stations"])
logger = logging.getLogger(__name__)


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
        # Search for station name or station code (e.g. NDLS)
        candidates = db.query(Stop).filter(
            (Stop.name.ilike(f"%{query_lower}%")) |
            (Stop.code.ilike(f"{query_lower}%")) |
            (Stop.stop_id.ilike(f"{query_lower}%"))
        ).limit(limit).all()

        results = [
            {"name": s.name, "code": s.code or s.stop_id, "city": s.city, "state": s.state}
            for s in candidates
        ]
        
        # If no results in Stop, fallback to StationMaster if it exists (for backward compatibility)
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
