"""
Station matching and resolution utilities for handling user input.
Uses PostgreSQL trigram indices for fuzzy matching.
"""
import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from backend.models import Stop

logger = logging.getLogger(__name__)


def resolve_station_by_name(db: Session, station_name: str) -> Optional[Stop]:
    """
    Resolve a station by name with fuzzy matching support.
    
    Tries:
    1. Exact match (case-insensitive)
    2. Code match (e.g., NDLS for New Delhi)
    3. Fuzzy match using trigram similarity (PostgreSQL only)
    4. Partial match (LIKE)
    
    Args:
        db: Database session
        station_name: Name, code, or abbreviation of station
        
    Returns:
        Stop object if found, None otherwise
    """
    if not station_name or len(station_name.strip()) == 0:
        return None
    
    name_clean = station_name.strip()
    
    # 1. Try exact match (case-insensitive)
    stop = db.query(Stop).filter(
        func.lower(Stop.name) == func.lower(name_clean)
    ).first()
    if stop:
        logger.debug(f"Found stop by exact name match: {stop.name}")
        return stop
    
    # 2. Try code match (for station codes like NDLS, CSMT, etc.)
    # Search both 'code' and 'stop_id'
    stop = db.query(Stop).filter(
        or_(Stop.code == name_clean.upper(), Stop.stop_id == name_clean.upper())
    ).first()
    if stop:
        logger.debug(f"Found stop by code match: {stop.code or stop.stop_id}")
        return stop
    
    # 3. Try fuzzy match using trigram similarity (PostgreSQL specific)
    try:
        from sqlalchemy import text
        # Use word_similarity for better PostgreSQL trigram matching
        similarity_threshold = 0.3  # Adjust based on tolerance
        
        stop = db.query(Stop).filter(
            func.word_similarity(Stop.name, name_clean) > similarity_threshold
        ).order_by(
            func.word_similarity(Stop.name, name_clean).desc()
        ).first()
        
        if stop:
            logger.debug(f"Found stop by fuzzy match: {stop.name} (input: {station_name})")
            return stop
    except Exception as e:
        logger.warning(f"Fuzzy matching failed (PostgreSQL trigram may not be enabled): {e}")
    
    # 4. Try partial match (LIKE with wildcards)
    stop = db.query(Stop).filter(
        Stop.name.ilike(f"%{name_clean}%")
    ).first()
    if stop:
        logger.debug(f"Found stop by partial match: {stop.name}")
        return stop
    
    logger.warning(f"Station not found: {station_name}")
    return None


def find_stations_by_partial_name(db: Session, partial_name: str, limit: int = 10) -> List[Stop]:
    """
    Find multiple stations matching a partial name (for autocomplete).
    
    Args:
        db: Database session
        partial_name: Partial station name
        limit: Maximum results to return
        
    Returns:
        List of Stop objects
    """
    if not partial_name or len(partial_name.strip()) < 2:
        return []
    
    name_clean = partial_name.strip()
    
    try:
        # Use trigram similarity for autocomplete if available
        from sqlalchemy import text
        results = db.query(Stop).filter(
            Stop.name.ilike(f"{name_clean}%")
        ).order_by(
            func.word_similarity(Stop.name, name_clean).desc()
        ).limit(limit).all()
        
        if results:
            logger.debug(f"Found {len(results)} stations for autocomplete: {name_clean}")
            return results
    except Exception as e:
        logger.debug(f"Trigram search failed: {e}, falling back to LIKE")
    
    # Fallback to LIKE matching
    results = db.query(Stop).filter(
        Stop.name.ilike(f"{name_clean}%")
    ).limit(limit).all()
    
    logger.debug(f"Found {len(results)} stations for autocomplete (LIKE): {name_clean}")
    return results


def resolve_stations(db: Session, source: str, destination: str) -> Tuple[Optional[Stop], Optional[Stop]]:
    """
    Resolve both source and destination stations.
    
    Args:
        db: Database session
        source: Source station name or code
        destination: Destination station name or code
        
    Returns:
        Tuple of (source_stop, dest_stop) or (None, None) if either is not found
    """
    source_stop = resolve_station_by_name(db, source)
    dest_stop = resolve_station_by_name(db, destination)
    
    if not source_stop:
        logger.warning(f"Could not resolve source station: {source}")
    if not dest_stop:
        logger.warning(f"Could not resolve destination station: {destination}")
    
    return source_stop, dest_stop


def validate_station_pair(source: Optional[Stop], destination: Optional[Stop]) -> bool:
    """
    Validate that both stations are properly resolved and different.
    
    Args:
        source: Source Stop object
        destination: Destination Stop object
        
    Returns:
        True if valid pair, False otherwise
    """
    if not source or not destination:
        return False
    
    if source.id == destination.id:
        logger.warning("Source and destination are the same station")
        return False
    
    return True
