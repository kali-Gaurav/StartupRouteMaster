"""
Client for IRCTC RapidAPI (irctc1.p.rapidapi.com).
Handles seat availability, fares, and quota lookups.
"""

import aiohttp
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class RapidAPIClient:
    """
    Async client for RapidAPI's IRCTC service with built-in concurrency control.
    [2.19] Supports API key rotation (delegated to RapidApiProvider).
    """
    
    def __init__(self, api_keys: str = "", max_concurrent: int = 2):
        try:
            from services.rapidapi_provider import rapidapi_provider
            self.provider = rapidapi_provider
        except ImportError:
            self.provider = None
            logger.error("RapidApiProvider not found - RapidAPIClient will fail")
        
        # Keep for backward compatibility
        self.api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]
        self._key_index = 0
        self.host = "irctc1.p.rapidapi.com"
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _get_current_headers(self) -> Dict[str, str]:
        """Rotates key and returns headers (legacy, no longer used internally)."""
        if not self.api_keys:
            return {}
        key = self.api_keys[self._key_index]
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return {
            "x-rapidapi-key": key,
            "x-rapidapi-host": self.host
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        from utils.http_client import HttpClientManager
        return await HttpClientManager.get_session()

    async def close(self):
        """No-op as session is managed globally."""
        pass

    def _format_date(self, date_str: str) -> str:
        if not date_str or "-" not in date_str:
            return date_str
        parts = date_str.split("-")
        if len(parts[0]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str

    async def get_seat_availability(self, train_no: str, from_stn: str, to_stn: str, date: str, quota: str = "GN", class_type: str = "SL") -> Optional[Dict[str, Any]]:
        if not self.provider: return None
        try:
            # rapidapi_provider already handles versioning and semaphores internally
            # Map legacy call to provider
            res = await self.provider.check_seat_availability(
                train_no=train_no, from_station=from_stn, to_station=to_stn,
                date=self._format_date(date), quota=quota, class_type=class_type
            )
            if res:
                # Return in expected format (dict)
                availability_list = []
                for item in res.availability:
                     if hasattr(item, "model_dump"):
                         availability_list.append(item.model_dump(by_alias=True))
                     else:
                         availability_list.append(item.dict(by_alias=True))
                
                return {"status": "success", "data": availability_list}
        except Exception as e:
            logger.error(f"RapidAPIClient wrapper error (seat): {e}")
        return None

    async def get_fare(self, train_no: str, from_stn: str, to_stn: str) -> Optional[Dict[str, Any]]:
        if not self.provider: return None
        try:
            res = await self.provider.get_fare(train_no, from_stn, to_stn)
            if res:
                if hasattr(res, "model_dump"):
                    return {"status": "success", "data": res.model_dump(by_alias=True)}
                return {"status": "success", "data": res.dict(by_alias=True)}
        except Exception as e:
            logger.error(f"RapidAPIClient wrapper error (fare): {e}")
        return None

    async def get_live_status(self, train_no: str) -> Optional[Dict[str, Any]]:
        if not self.provider: return None
        try:
            # Calling default start_day=1 for legacy compatibility
            res = await self.provider.get_live_train_status(train_no, 1)
            if res:
                if hasattr(res, "model_dump"):
                    return {"status": "success", "data": res.model_dump(by_alias=True)}
                return {"status": "success", "data": res.dict(by_alias=True)}
        except Exception as e:
            logger.error(f"RapidAPIClient wrapper error (live): {e}")
        return None
