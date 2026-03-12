from typing import List, Optional, Tuple, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import logging

from database.models import Stop
from services.station_search_service import station_search_engine
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

def resolve_stations(db: Session, source_query: str, dest_query: str) -> Tuple[Optional[Stop], Optional[Stop]]:
    """
    Resolves source and destination queries to canonical Stop objects.
    Uses Redis Cache, then Postgres (Supabase), then StationSearchEngine.
    """
    def find_one(query: str) -> Optional[Stop]:
        if not query: return None
        q = query.strip().upper()
        
        # 1. Task 5.1: Redis Cache Check
        cache_key = f"station_resolve:{q}"
        try:
            cached = cache_service.get(cache_key)
            if cached:
                return Stop(
                    stop_id=cached.get("stop_id"),
                    code=cached.get("code"),
                    name=cached.get("name"),
                    city=cached.get("city"),
                    state=cached.get("state"),
                    latitude=cached.get("latitude", 0.0),
                    longitude=cached.get("longitude", 0.0)
                )
        except Exception: pass
        
        # 2. Try Postgres (Supabase) Stop table - Exact Code or stop_id
        stop = db.query(Stop).filter(or_(Stop.stop_id == q, Stop.code == q)).first()
        
        # 3. Try exact name match in Postgres
        if not stop:
            stop = db.query(Stop).filter(func.upper(Stop.name) == q).first()

        # 4. Fallback to StationSearchEngine (transit_graph.db)
        if not stop:
            resolved = station_search_engine.resolve(query)
            if resolved:
                stop = Stop(
                    stop_id=resolved.code,
                    code=resolved.code,
                    name=resolved.name,
                    city=resolved.city,
                    state=resolved.state,
                    latitude=resolved.lat,
                    longitude=resolved.lon
                )
        
        # 5. Cache result if found
        if stop:
            try:
                stop_data = {
                    "stop_id": stop.stop_id, "code": stop.code, "name": stop.name,
                    "city": stop.city, "state": stop.state, 
                    "latitude": stop.latitude, "longitude": stop.longitude
                }
                cache_service.set(cache_key, stop_data, ttl_seconds=86400) # 24h
            except Exception: pass
            
        return stop

    src = find_one(source_query)
    dst = find_one(dest_query)
    
    if not src: logger.warning(f"Resolution Failed: source station '{source_query}' not found.")
    if not dst: logger.warning(f"Resolution Failed: destination station '{dest_query}' not found.")
    
    return src, dst

def find_stations_by_partial_name(db: Session, query: str, limit: int = 10) -> List[Stop]:
    """
    High-speed autocomplete helper. 
    Redirects to StationSearchEngine for production performance.
    """
    if len(query) < 2: return []
    
    # We use the optimized engine for all autocomplete requests
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
