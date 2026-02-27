"""
SeatAvailabilityManager orchestrates real-time availability lookups,
caching, route unlocking logic, and API budget management.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from .rapid_api_client import RapidAPIClient

from sqlalchemy.orm import Session
from database.models import SeatAvailability
from database.session import SessionLocal
logger = logging.getLogger(__name__)

class SeatAvailabilityManager:
    """
    Manages seat availability lifecycle for search results.
    """
    
    def __init__(self, rapid_client: RapidAPIClient, cache_ttl_minutes: int = 15):
        self.api = rapid_client
        self.cache_ttl = cache_ttl_minutes * 60 # Convert to seconds for Redis
        self.default_daily_limit = 200

    async def get_availability(
        self, 
        train_no: str, 
        from_stn: str, 
        to_stn: str, 
        date: str, 
        quota: str = "GN", 
        class_type: str = "SL",
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves availability with distributed caching and budget protection.
        """
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.initialize()
        
        # 1. Check Usage Budget (Distributed check)
        api_name = "rapid_api_irctc1"
        if not await self._check_budget_redis(api_name):
            logger.warning(f"API budget '{api_name}' reached. Returning degraded response.")
            return {"status": "degraded", "message": "API Limit Reached", "data": None}

        # 2. Check Distributed Cache
        cache_key = self._generate_cache_key(train_no, from_stn, to_stn, date, quota, class_type)
        if not force_refresh:
            cached_data = await multi_layer_cache.get(cache_key)
            if cached_data:
                logger.debug(f"Distributed Cache Hit for {cache_key}")
                return cached_data

        # 3. Call API
        logger.info(f"Cache Miss for {cache_key}. Calling RapidAPI.")
        data = await self.api.get_seat_availability(train_no, from_stn, to_stn, date, quota, class_type)
        
        if data:
            # 4. Increment usage in Redis and Sync to DB periodically
            await self._increment_budget_redis(api_name)
            
            # 5. Log for ML (Moat Dataset) - Keep DB log but make it async-friendly
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._log_availability_sync, train_no, quota, class_type, date, data)
            
            # 6. Save to Distributed Cache
            await multi_layer_cache.set(cache_key, data, ttl_seconds=self.cache_ttl)
            return data
            
        return None

    def _log_availability_sync(self, train_no, quota, class_type, date, data):
        """Synchronous wrapper for database logging to be run in executor."""
        session = SessionLocal()
        try:
            self._log_availability_for_ml(session, train_no, quota, class_type, date, data)
        finally:
            session.close()

    async def _check_budget_redis(self, api_name: str) -> bool:
        """Checks if the daily API budget is exceeded using Redis for speed."""
        from core.redis import redis_client
        from datetime import date
        today_key = f"api_usage:{api_name}:{date.today().isoformat()}"
        
        try:
            count = redis_client.get(today_key)
            if count and int(count) >= self.default_daily_limit:
                return False
        except Exception:
            pass # Fallback to true if redis fails
        return True

    async def _increment_budget_redis(self, api_name: str):
        """Increments the daily API usage count in Redis."""
        from core.redis import redis_client
        from datetime import date
        today_key = f"api_usage:{api_name}:{date.today().isoformat()}"
        try:
            redis_client.incr(today_key)
            redis_client.expire(today_key, 86400) # 24h TTL
        except Exception:
            pass

    def _log_availability_for_ml(self, session: Session, train_no: str, quota: str, class_type: str, travel_date_str: str, data: Dict[str, Any]):
        """
        Logs longitudinal availability data to build the predictive dataset.
        Extracts WL numbers if present.
        """
        try:
            # Parse travel date
            try:
                travel_date = datetime.strptime(travel_date_str, "%Y-%m-%d")
            except:
                travel_date = datetime.utcnow() # Fallback

            # IRCTC1 API v1 structure: data['data']['availability'] is usually a list
            avail_list = data.get("data", {}).get("availability", [])
            if not avail_list and isinstance(data.get("data"), list):
                avail_list = data["data"]

            for entry in avail_list:
                # Extract WL number if possible (e.g., 'RLWL/10' -> 10)
                status = entry.get("status", "")
                wl_num = None
                if "WL" in status:
                    import re
                    match = re.search(r'WL\s*(\d+)', status)
                    if not match:
                        match = re.search(r'/(\d+)', status)
                    if match:
                        wl_num = int(match.group(1))

                log_entry = SeatAvailability(
                    train_number=train_no,
                    class_code=class_type,
                    quota=quota,
                    availability_status=status,
                    waiting_list_number=wl_num,
                    fare=float(data.get("data", {}).get("fare", 0)) or None,
                    travel_date=travel_date,
                    check_date=datetime.utcnow()
                )
                session.add(log_entry)
            
            session.commit()
            logger.info(f"Logged {len(avail_list)} availability records for ML (Train: {train_no})")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log ML availability: {e}")

    def get_route_locks(self, routes: List[Dict[str, Any]], unlock_count: int = 3) -> List[Dict[str, Any]]:
        """
        Marks first N routes as unlocked, others as locked.
        """
        for i, route in enumerate(routes):
            route["is_locked"] = i >= unlock_count
        return routes

    async def prefetch_top_routes(self, routes: List[Dict[str, Any]], count: int = 2):
        """
        Silently fetch availability for top routes to ensure 'instant' perception.
        Ensures both SL and 3A are cached.
        """
        top_routes = routes[:count]
        tasks = []
        # Multi-class prefetching (Point 6)
        classes = ["SL", "3A"]
        
        for route in top_routes:
            train_no = route.get("train_number")
            from_stn = route.get("from_station")
            to_stn = route.get("to_station")
            date = route.get("date")
            
            if train_no and from_stn and to_stn and date:
                for cls in classes:
                    tasks.append(self.get_availability(train_no, from_stn, to_stn, date, class_type=cls))
        
        if tasks:
            logger.info(f"Prefetching {len(tasks)} availability checks background...")
            await asyncio.gather(*tasks, return_exceptions=True)

    def _get_usage(self, session: Session, api_name: str):
        """Fetches or creates the daily usage record for an API."""
        from database.models import APIUsage
        from datetime import date
        today = date.today()
        
        usage = session.query(APIUsage).filter(
            APIUsage.api_name == api_name,
            APIUsage.date == today
        ).first()
        
        if not usage:
            usage = APIUsage(
                api_name=api_name,
                date=today,
                daily_limit=self.default_daily_limit,
                request_count=0
            )
            session.add(usage)
            session.flush()
            
        return usage

    def _generate_cache_key(self, train_no, from_stn, to_stn, date, quota, class_type):
        """Standardized cache key for seat availability."""
        return f"avail:{train_no}:{from_stn}:{to_stn}:{date}:{quota}:{class_type}"
