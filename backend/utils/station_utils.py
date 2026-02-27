from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging

from database.models import Stop

logger = logging.getLogger(__name__)

def resolve_stations(db: Session, source_query: str, dest_query: str) -> Tuple[Optional[Stop], Optional[Stop]]:
    """
    Resolves source and destination queries to canonical Stop objects.
    Tries exact code match first, then name/city match.
    """
    def find_one(query: str) -> Optional[Stop]:
        if not query: return None
        q = query.strip().upper()
        
        # 1. Try exact code match (fastest)
        stop = db.query(Stop).filter(or_(Stop.stop_id == q, Stop.code == q)).first()
        if stop: return stop
        
        # 2. Try name/city match
        stop = db.query(Stop).filter(or_(Stop.name.ilike(f"%{query}%"), Stop.city.ilike(f"%{query}%"))).first()
        return stop

    src = find_one(source_query)
    dst = find_one(dest_query)
    
    if not src: logger.warning(f"Could not resolve source: {source_query}")
    if not dst: logger.warning(f"Could not resolve destination: {dest_query}")
    
    return src, dst

def find_stations_by_partial_name(db: Session, query: str, limit: int = 10) -> List[Stop]:
    """Helper for autocomplete."""
    if len(query) < 2: return []
    return db.query(Stop).filter(
        or_(
            Stop.name.ilike(f"%{query}%"),
            Stop.stop_id.ilike(f"{query}%"),
            Stop.code.ilike(f"{query}%")
        )
    ).limit(limit).all()
