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
    """
    
    BASE_URL = "https://irctc1.p.rapidapi.com/api/v1" 
    
    def __init__(self, api_key: str, max_concurrent: int = 2):
        self.api_key = api_key
        self.host = "irctc1.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host
        }
        
        # respect preferred version from config if provided
        try:
            from database.config import Config
            pref = getattr(Config, "RAPIDAPI_PREFERRED_VERSION", "v1")
            self.preferred_version = pref.lower() if pref else "v1"
        except:
            self.preferred_version = "v1"
            
        # Task 21.6: Semaphore to prevent rate-limiting issues
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _format_date(self, date_str: str) -> str:
        """Ensure the date is in DD-MM-YYYY format."""
        if not date_str or "-" not in date_str:
            return date_str
        parts = date_str.split("-")
        if len(parts[0]) == 4:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str

    async def get_seat_availability(self, train_no: str, from_stn: str, to_stn: str, date: str, quota: str = "GN", class_type: str = "SL") -> Optional[Dict[str, Any]]:
        """
        Fetch seat availability and fare for a specific train.
        Endpoint: /checkSeatAvailability
        """
        async with self._semaphore:
            ver = self.preferred_version
            endpoint = f"https://{self.host}/api/{ver}/checkSeatAvailability"
            params = {
                "classType": class_type, 
                "fromStationCode": from_stn,
                "quota": quota,
                "toStationCode": to_stn,
                "trainNo": train_no,
                "date": self._format_date(date)
            }
            
            try:
                session = await self._get_session()
                async with session.get(endpoint, params=params, timeout=15) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        logger.warning("RapidAPI Rate Limit Exceeded.")
                        return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}
                    else:
                        error_text = await response.text()
                        logger.error(f"RapidAPI Error {response.status}: {error_text}")
                        return None
            except Exception as e:
                logger.error(f"Failed to fetch seat availability: {str(e)}")
                return None

    async def get_fare(self, train_no: str, from_stn: str, to_stn: str) -> Optional[Dict[str, Any]]:
        """
        Fetch fare details.
        Endpoint: /getFare
        """
        async with self._semaphore:
            endpoint = f"{self.BASE_URL}/getFare"
            params = {
                "trainNo": train_no,
                "fromStationCode": from_stn,
                "toStationCode": to_stn
            }
            
            try:
                session = await self._get_session()
                async with session.get(endpoint, params=params, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
            except Exception as e:
                logger.error(f"Failed to fetch fare: {str(e)}")
                return None
