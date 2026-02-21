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
from routemaster_agent.database.models import APIBudget, SeatAvailability
from routemaster_agent.database.db import SessionLocal

logger = logging.getLogger(__name__)

class SeatAvailabilityManager:
    """
    Manages seat availability lifecycle for search results.
    """
    
    def __init__(self, rapid_client: RapidAPIClient, cache_ttl_minutes: int = 15):
        self.api = rapid_client
        self.cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {"data": data, "expiry": datetime}}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.default_daily_limit = 200

    def _get_usage(self, session: Session, api_name: str) -> APIBudget:
        """Get or create budget record for today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        budget = session.query(APIBudget).filter(
            APIBudget.api_name == api_name,
            APIBudget.usage_date == today
        ).first()
        
        if not budget:
            budget = APIBudget(
                api_name=api_name,
                usage_date=today,
                request_count=0,
                daily_limit=self.default_daily_limit
            )
            session.add(budget)
            session.commit()
            session.refresh(budget)
        return budget

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
        Retrieves availability with caching and budget protection.
        """
        session = SessionLocal()
        try:
            # 1. Check Usage Budget
            budget = self._get_usage(session, "rapid_api_irctc1")
            if budget.request_count >= budget.daily_limit:
                logger.warning(f"API budget '{budget.api_name}' reached ({budget.request_count}/{budget.daily_limit}).")
                return {"status": "degraded", "message": "API Limit Reached", "data": None}

            # 2. Check Cache
            cache_key = self._generate_cache_key(train_no, from_stn, to_stn, date, quota, class_type)
            if not force_refresh and cache_key in self.cache:
                entry = self.cache[cache_key]
                if datetime.now() < entry["expiry"]:
                    logger.info(f"Cache Hit for {cache_key}")
                    return entry["data"]
                else:
                    del self.cache[cache_key]

            # 3. Call API
            logger.info(f"Cache Miss for {cache_key}. Calling RapidAPI.")
            data = await self.api.get_seat_availability(train_no, from_stn, to_stn, date, quota, class_type)
            
            if data:
                # 4. Update usage
                budget.request_count += 1
                session.commit()
                
                # 5. Log for ML (Moat Dataset) - Priority 2
                self._log_availability_for_ml(session, train_no, quota, class_type, date, data)
                
                # 6. Save to Cache
                self.cache[cache_key] = {
                    "data": data,
                    "expiry": datetime.now() + self.cache_ttl
                }
                return data
                
            return None
        finally:
            session.close()

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
