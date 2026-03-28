from typing import List, Optional, Tuple, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import logging
import functools

from database.models import Stop
from services.station_search_service import station_search_engine
from services.cache_service import cache_service

import time
from collections import defaultdict

# [Gap 1] Database-driven Metropolitan Station Unification Map
# Fallback hardcoded groups for initial boot or if DB is empty (Task 121: Yield Expansion)
_FALLBACK_METRO_GROUPS = {
    "DELHI": ["NDLS", "NZM", "DLI", "DEE", "ANVT", "SZM", "DKZ"],
    "MUMBAI": ["MMCT", "BDTS", "CSMT", "DDR", "LTT", "BVI", "PNVL"],
    "CHENNAI": ["MAS", "MS", "TBM", "PER", "AJJ"],
    "KOLKATA": ["HWH", "KOAA", "SDAH", "SHM"],
    "BANGALORE": ["SBC", "YPR", "SMVB", "KJM"],
    "HYDERABAD": ["SC", "HYB", "KCG", "LPI"],
    "PUNE": ["PUNE", "HDP", "CCH"],
    "AHMEDABAD": ["ADI", "SBT", "GER"]
}

# In-memory cache for metro groups to prevent repeated DB hits
_metro_cache = {}
_last_metro_refresh = 0

@functools.lru_cache(maxsize=2048)
def get_metro_group_codes(station_code: str, db: Optional[Session] = None) -> List[str]:
    """
    Returns all station codes in the same metropolitan area.
    [Gap 1] Dynamically loads from metro_station_groups table with fallback.
    """
    global _metro_cache, _last_metro_refresh
    code = str(station_code).upper().strip()
    now = time.time()

    # Refresh cache every hour if DB is available
    if db and (not _metro_cache or (now - _last_metro_refresh > 3600)):
        try:
            from database.models import MetroStationGroup
            groups = db.query(MetroStationGroup).all()
            if groups:
                new_cache = defaultdict(list)
                for g in groups:
                    new_cache[g.group_name].append(g.station_code)
                _metro_cache = dict(new_cache)
                _last_metro_refresh = now
                logger.debug(f"🚄 Metro Cache Refreshed: {len(_metro_cache)} groups found in DB.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load Metro Groups from DB: {e}")

    # Use cache or fallback
    active_groups = _metro_cache if _metro_cache else _FALLBACK_METRO_GROUPS
    
    for group_name, codes in active_groups.items():
        if code in codes:
            return codes
    return [code]

import time
from collections import defaultdict

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
