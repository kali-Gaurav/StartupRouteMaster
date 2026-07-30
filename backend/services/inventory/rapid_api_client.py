import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import date
from database.config import Config

logger = logging.getLogger(__name__)

class RapidAPIClient:
    """
    Client for fetching real-time Indian Railways seat availability via RapidAPI.
    Used as the primary data source, falling back to local DB if unavailable.
    """
    
    def __init__(self):
        self.api_key = getattr(Config, "RAPID_API_KEY", None)
        self.base_url = "https://indian-railway-api.p.rapidapi.com/api/v1"
        self.headers = {
            "X-RapidAPI-Key": self.api_key or "demo-key",
            "X-RapidAPI-Host": "indian-railway-api.p.rapidapi.com"
        }
        
    async def get_seat_availability(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        date: date,
        class_type: str,
        quota: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch seat availability from RapidAPI."""
        if not self.api_key:
            logger.warning("RAPID_API_KEY not configured, skipping real-time fetch.")
            return None
            
        endpoint = f"{self.base_url}/checkSeatAvailability"
        params = {
            "trainNo": train_number,
            "sourceStation": from_station,
            "destinationStation": to_station,
            "date": date.strftime("%Y-%m-%d"),
            "classType": class_type,
            "quota": quota
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=self.headers, params=params, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == True:
                            return data.get("data")
                    logger.warning(f"RapidAPI request failed with status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"RapidAPI fetch error: {e}")
            return None

rapid_api_client = RapidAPIClient()
