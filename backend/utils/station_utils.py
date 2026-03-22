from typing import List, Optional, Tuple, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import logging
import functools

from database.models import Stop
from services.station_search_service import station_search_engine
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

# [Task 27.15] Metropolitan Station Unification Map
# Maps station codes to their logical metropolitan groups to maximize search yield.
METRO_GROUPS = {
    "DELHI": ["NDLS", "NZM", "DLI", "DEE", "ANVT", "SZM", "DKZ"],
    "MUMBAI": ["MMCT", "BDTS", "CSMT", "DDR", "LTT", "BVI", "PNVL"],
    "CHENNAI": ["MAS", "MS", "TBM", "PER", "AJJ"],
    "KOLKATA": ["HWH", "KOAA", "SDAH", "SHM"],
    "BANGALORE": ["SBC", "YPR", "SMVB", "KJM"]
}

def get_metro_group_codes(station_code: str) -> List[str]:
    """Returns all station codes in the same metropolitan area."""
    code = str(station_code).upper().strip()
    for group, codes in METRO_GROUPS.items():
        if code in codes:
            return codes
    return [code]

@functools.lru_cache(maxsize=1024)
def resolve_stations(db: Session, source_query: str, dest_query: str) -> Tuple[Optional[Stop], Optional[Stop]]:
    """
    Subtask 1.6: Optimized station resolution with multi-layer caching.
    Supports station code, GTFS ID, or full name.
    """
    def _resolve_single(query: str) -> Optional[Stop]:
        if not query: return None
        q = query.upper().strip()
        
        # 1. L1 Cache (Local)
        # Done via lru_cache decorator on the outer function
        
        # 2. L2 Cache (Redis)
        cache_key = f"station_resolve:{q}"
        try:
            cached = cache_service.get(cache_key)
            if cached and cached.get("id") is not None:
                # Fill L1 from L2
                return Stop(
                    id=cached.get("id"),
                    stop_id=cached.get("stop_id"),
                    code=cached.get("code"),
                    name=cached.get("name"),
                    city=cached.get("city"),
                    state=cached.get("state"),
                    latitude=cached.get("latitude", 0.0),
                    longitude=cached.get("longitude", 0.0)
                )
        except Exception: pass
        
        # 3. Database & Engine Fallback
        stop = db.query(Stop).filter(or_(Stop.stop_id == q, Stop.code == q)).first()
        if not stop:
            stop = db.query(Stop).filter(func.upper(Stop.name) == q).first()
        if not stop:
            resolved = station_search_engine.resolve(query)
            if resolved:
                # Still need to fetch numeric ID from DB even if resolved via engine
                stop = db.query(Stop).filter(Stop.code == resolved.code).first()
                if not stop:
                    stop = Stop(
                        stop_id=resolved.code,
                        code=resolved.code,
                        name=resolved.name,
                        city=resolved.city, state=resolved.state,
                        latitude=resolved.latitude, longitude=resolved.longitude
                    )
        
        # 4. Populate Caches
        if stop:
            stop_data = {
                "id": stop.id, "stop_id": stop.stop_id, "code": stop.code, "name": stop.name,
                "city": stop.city, "state": stop.state, 
                "latitude": stop.latitude, "longitude": stop.longitude
            }
            try:
                cache_service.put(cache_key, stop_data, ttl=86400) # 24h
            except Exception: pass
            
        return stop

    return _resolve_single(source_query), _resolve_single(dest_query)

def get_station_by_code(db: Session, code: str) -> Optional[Stop]:
    """Helper to fetch a single stop by code."""
    return db.query(Stop).filter(Stop.code == code.upper()).first()

def find_stations_by_partial_name(db: Session, query: str, limit: int = 10) -> List[Stop]:
    """
    High-speed autocomplete helper. 
    Redirects to StationSearchEngine for production performance.
    """
    if len(query) < 2: return []
    
    suggestions = station_search_engine.suggest(query, limit=limit)
    
    return [
        Stop(
            stop_id=s.code,
            code=s.code,
            name=s.name,
            city=s.city,
            state=s.state
        ) for s in suggestions
    ]
