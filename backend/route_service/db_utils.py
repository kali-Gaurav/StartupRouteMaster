import redis
import os
import json
from typing import Optional
import logging

from sqlalchemy.orm import Session
from backend.models import Stop

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Cache TTL for static data (e.g., 1 hour)
STATIC_DATA_CACHE_TTL = 3600

def get_stop_by_id_cached(db: Session, stop_id: int) -> Optional[Stop]:
    """
    Fetches a Stop object by its ID, first checking Redis cache.
    Caches the result in Redis if not found there.
    """
    cache_key = f"stop:{stop_id}"
    
    # 1. Check Redis cache
    cached_stop_data = redis_client.get(cache_key)
    if cached_stop_data:
        try:
            logger.info(f"Cache hit for stop_id: {stop_id}")
            data = json.loads(cached_stop_data)
            # Reconstruct Stop object from cached data
            # This is a simplified reconstruction. In a real app, you might
            # use pydantic models or a more robust deserialization.
            stop = Stop(
                id=data['id'],
                stop_id=data['stop_id'],
                name=data['name'],
                code=data['code'],
                city=data['city'],
                state=data['state'],
                latitude=data['latitude'],
                longitude=data['longitude'],
                # geom cannot be directly reconstructed this way
            )
            # Assign other attributes if needed
            return stop
        except Exception as e:
            logger.error(f"Error deserializing cached stop data for {stop_id}: {e}")
            redis_client.delete(cache_key) # Invalidate corrupted cache
    
    # 2. If not in cache, fetch from DB
    logger.info(f"Cache miss for stop_id: {stop_id}, fetching from DB.")
    stop = db.query(Stop).filter(Stop.id == stop_id).first() # Note: Stop.id is PK, use Stop.stop_id if querying by GTFS stop_id string
    
    if stop:
        # 3. Store in Redis cache
        # Convert SQLAlchemy object to dict for caching
        data_to_cache = {
            "id": stop.id,
            "stop_id": stop.stop_id,
            "name": stop.name,
            "code": stop.code,
            "city": stop.city,
            "state": stop.state,
            "latitude": stop.latitude,
            "longitude": stop.longitude,
            # geom is not easily serializable to JSON, omit for basic caching
        }
        redis_client.setex(cache_key, STATIC_DATA_CACHE_TTL, json.dumps(data_to_cache))
    
    return stop

# Additional caching functions for other static data types (e.g., Routes) can be added here
