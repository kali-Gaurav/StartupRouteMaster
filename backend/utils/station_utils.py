from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import logging

from database.models import Stop
from services.station_search_service import station_search_engine

logger = logging.getLogger(__name__)

def resolve_stations(db: Session, source_query: str, dest_query: str) -> Tuple[Optional[Stop], Optional[Stop]]:
    """
    Resolves source and destination queries to canonical Stop objects.
    Uses Postgres (Supabase) Stop table first, then falls back to 
    optimized StationSearchEngine powered by transit_graph.db.
    """
    def find_one(query: str) -> Optional[Stop]:
        if not query: return None
        q = query.strip().upper()
        
        # 1. Try Postgres (Supabase) Stop table - Exact Code or stop_id
        stop = db.query(Stop).filter(or_(Stop.stop_id == q, Stop.code == q)).first()
        if stop: return stop
        
        # 2. Try exact name match in Postgres
        stop = db.query(Stop).filter(func.upper(Stop.name) == q).first()
        if stop: return stop

        # 3. Fallback to high-performance StationSearchEngine (transit_graph.db)
        # This ensures resolution even if Postgres synchronization is pending.
        resolved = station_search_engine.resolve(query)
        if resolved:
            logger.info(f"Resolved '{query}' via TransitGraph engine: {resolved.code}")
            
            # Check if this stop exists in Postgres to maintain ORM consistency
            stop_model = db.query(Stop).filter(or_(Stop.stop_id == resolved.code, Stop.code == resolved.code)).first()
            if stop_model:
                return stop_model
            
            # Construct a transient Stop object from TransitGraph data 
            # if missing in Postgres (prevents search failure)
            return Stop(
                stop_id=resolved.code,
                code=resolved.code,
                name=resolved.name,
                city=resolved.city,
                state=resolved.state
            )
        
        return None

    src = find_one(source_query)
    dst = find_one(dest_query)
    
    if not src: logger.warning(f"Resolution Failed: source station '{source_query}' not found in Supabase or TransitGraph.")
    if not dst: logger.warning(f"Resolution Failed: destination station '{dest_query}' not found in Supabase or TransitGraph.")
    
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
