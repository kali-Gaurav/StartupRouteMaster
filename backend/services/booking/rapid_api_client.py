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
    Async client for RapidAPI's IRCTC service.
    """
    
    BASE_URL = "https://irctc1.p.rapidapi.com/api/v1"  # Updated to V1 as per recommendation
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.host = "irctc1.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host
        }

    async def get_seat_availability(self, train_no: str, from_stn: str, to_stn: str, date: str, quota: str = "GN", class_type: str = "SL") -> Optional[Dict[str, Any]]:
        """
        Fetch seat availability and fare for a specific train.
        Endpoint: /checkSeatAvailability
        """
        endpoint = f"{self.BASE_URL}/checkSeatAvailability"
        params = {
            "classType": class_type,  # V1 uses camelCase
            "fromStationCode": from_stn,
            "quota": quota,
            "toStationCode": to_stn,
            "trainNo": train_no,
            "date": date
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=self.headers, params=params, timeout=10) as response:
                    # Point 10: Robust Error Handling
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
        endpoint = f"{self.BASE_URL}/getFare"
        params = {
            "trainNo": train_no,
            "fromStationCode": from_stn,
            "toStationCode": to_stn
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=self.headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch fare: {str(e)}")
            return None
