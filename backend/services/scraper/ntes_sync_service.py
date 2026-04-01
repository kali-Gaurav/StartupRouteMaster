import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.session import AsyncSessionTransit
from database.models import TrainRunningStatusCache
from core.redis import async_redis_client

logger = logging.getLogger("service.ntes_sync")

class NtesSyncService:
    """
    Handles persistence and multi-layer caching for NTES scraped data.
    Ensures 'RouteMaster' has fast access to validated running status.
    """

    @staticmethod
    async def upsert_status(train_number: str, journey_date: date, data: Dict[str, Any]):
        """
        Upserts the scraped data into the database and updates Redis.
        [Task 48.9 & 48.10]
        """
        try:
            # 1. Update Redis (for extremely fast retrieval)
            cache_key = f"status:ntes:{train_number}:{journey_date.isoformat()}"
            await async_redis_client.setex(cache_key, 180, str(data)) # 3 Min TTL
            
            # 2. Update Database (for persistence and history)
            async with AsyncSessionTransit() as session:
                # PostgreSQL UPSERT logic
                stmt = pg_insert(TrainRunningStatusCache).values(
                    train_number=train_number,
                    journey_date=journey_date,
                    current_station=data.get("current_station", "N/A"),
                    delay_minutes=data.get("delay_minutes", 0),
                    running_status_text=data.get("delay_info", "N/A"),
                    data_payload=data.get("full_table", []),
                    last_updated_at=datetime.utcnow()
                ).on_conflict_do_update(
                    constraint="uix_train_date",
                    set_={
                        "current_station": data.get("current_station", "N/A"),
                        "delay_minutes": data.get("delay_minutes", 0),
                        "running_status_text": data.get("delay_info", "N/A"),
                        "data_payload": data.get("full_table", []),
                        "last_updated_at": datetime.utcnow()
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
                
            logger.info(f"✅ Synced status for {train_number} ({journey_date}) to DB and Cache.")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to sync NTES status for {train_number}: {e}")
            return False

    @staticmethod
    async def get_cached_status(train_number: str, journey_date: date) -> Optional[Dict[str, Any]]:
        """
        Retrieves status from Redis or Database if fresh enough (< 3 mins).
        """
        cache_key = f"status:ntes:{train_number}:{journey_date.isoformat()}"
        
        # 1. Check Redis
        cached_raw = await async_redis_client.get(cache_key)
        if cached_raw:
            try:
                # Assuming data was stored as stringified dict
                return eval(cached_raw) 
            except:
                pass
        
        # 2. Check Database
        async with AsyncSessionTransit() as session:
            query = select(TrainRunningStatusCache).filter(
                TrainRunningStatusCache.train_number == train_number,
                TrainRunningStatusCache.journey_date == journey_date
            )
            result = await session.execute(query)
            status = result.scalar_one_or_none()
            
            if status:
                # Only return if fresh enough (e.g., < 2 minutes)
                age = (datetime.utcnow() - status.last_updated_at).total_seconds()
                if age < 120:
                    return {
                        "current_station": status.current_station,
                        "delay_info": status.running_status_text,
                        "delay_minutes": status.delay_minutes,
                        "full_table": status.data_payload,
                        "last_updated": status.last_updated_at.isoformat()
                    }
        
        return None

ntes_sync_service = NtesSyncService()
