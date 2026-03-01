import aiohttp
import logging
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
from database.config import Config
from core.redis import async_redis_client

logger = logging.getLogger(__name__)

# Request coalescing for live status
_inflight_live_status: Dict[str, asyncio.Future] = {}

class LiveStatusService:
    """
    Service to fetch live train status from Rappid.in or other live sources.
    Handles parsing and normalization of external API data with caching and persistent sessions.
    """
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self):
        self.base_url = Config.LIVE_STATUS_BASE_URL
        self.enabled = Config.ENABLE_LIVE_STATUS
        self.cache_ttl = 60 # Cache live status for 60 seconds

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5),
                connector=aiohttp.TCPConnector(limit=100)
            )
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    async def get_live_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetches live status for a specific train number, using Redis cache and persistent session.
        """
        if not self.enabled:
            return None

        cache_key = f"live_status:{train_number}"
        
        # 1. Check Cache First
        try:
            cached = await async_redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache error on live status: {e}")

        # 2. Request Coalescing (Single-Flight)
        if cache_key in _inflight_live_status:
            return await _inflight_live_status[cache_key]

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        _inflight_live_status[cache_key] = future

        try:
            result = await self._execute_fetch(train_number, cache_key)
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            if cache_key in _inflight_live_status:
                del _inflight_live_status[cache_key]

    async def _execute_fetch(self, train_number: str, cache_key: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}"
        params = {"train_no": train_number}

        try:
            session = await self.get_session()
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Live status API error {response.status} for {train_number}")
                    return None
                
                data = await response.json()
                
                if not data.get("success"):
                    return None
                    
                normalized_data = self._normalize_response(data, train_number)
                
                # 3. Save to Cache
                try:
                    await async_redis_client.setex(cache_key, self.cache_ttl, json.dumps(normalized_data))
                except Exception as e:
                    pass
                    
                return normalized_data

        except Exception as e:
            logger.error(f"Exception during live status fetch for {train_number}: {e}")
            return None

    def _normalize_response(self, data: Dict[str, Any], train_number: str) -> Dict[str, Any]:
        """
        Normalizes external API data to RouteMaster's internal format.
        """
        return {
            "train_number": train_number,
            "train_name": data.get("train_name", "Unknown"),
            "current_station_name": data.get("current_station", "Unknown"),
            "delay_minutes": int(data.get("delay", 0)),
            "status_message": data.get("status_message", "In Transit"),
            "last_updated": data.get("last_updated", datetime.utcnow().isoformat()),
            "source": "RappidAPI Live",
            "raw_data": data
        }
