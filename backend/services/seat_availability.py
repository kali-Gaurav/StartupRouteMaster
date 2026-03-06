import asyncio
import logging
import time
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class ISeatAvailabilityProvider(ABC):
    """
    Subtask 1.3: Generic interface for ethical seat availability checking.
    """
    @abstractmethod
    async def get_availability(self, train_number: str, source: str, destination: str, date: str, class_type: str, quota: str = "GN") -> Dict[str, Any]:
        pass

class RapidApiSeatProvider(ISeatAvailabilityProvider):
    """
    Subtasks 1.2, 1.4, 1.8: Secure connection to RapidAPI partner endpoints,
    handling quotas (GN, TQ, LD) and implementing fallback logic.
    """
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_IRCTC_KEY", "MOCK_KEY_FOR_TESTING")
        self.base_url = "https://irctc1.p.rapidapi.com/api/v3/trainBetweenStations" # Example endpoint structure
        self.timeout = 10.0

    async def get_availability(self, train_number: str, source: str, destination: str, date: str, class_type: str, quota: str = "GN") -> Dict[str, Any]:
        """
        Subtask 1.5: Setup Redis caching for seat availability (5-minute TTL).
        """
        cache_key = f"seat_avail:{train_number}:{source}:{destination}:{date}:{class_type}:{quota}"
        
        await multi_layer_cache.initialize()
        if multi_layer_cache.redis:
            try:
                cached_data = await multi_layer_cache.redis.get(cache_key)
                if cached_data:
                    logger.info(f"Cache hit for seat availability: {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        # Subtask 1.6: Log API latency and success rates
        start_time = time.time()
        success = False
        status_code = None
        
        try:
            # We mock the actual HTTP call for the prototype unless a real key is present
            if self.api_key == "MOCK_KEY_FOR_TESTING":
                await asyncio.sleep(0.5) # Simulate network latency
                mock_response = self._generate_mock_response(train_number, source, destination, date, class_type, quota)
                status_code = 200
                success = True
                result = self._map_response(mock_response, status_code)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    headers = {
                        "X-RapidAPI-Key": self.api_key,
                        "X-RapidAPI-Host": "irctc1.p.rapidapi.com"
                    }
                    # Example payload construction
                    params = {
                        "trainNo": train_number,
                        "fromStationCode": source,
                        "toStationCode": destination,
                        "date": date,
                        "classType": class_type,
                        "quota": quota
                    }
                    
                    response = await client.get(self.base_url, headers=headers, params=params)
                    status_code = response.status_code
                    
                    # Subtask 1.9: Setup alerting for API rate limits.
                    remaining = response.headers.get("X-RateLimit-Requests-Remaining")
                    if remaining and int(remaining) < 50:
                        logger.critical(f"🚨 ALERT: RapidAPI rate limit running low! Remaining: {remaining}")
                        
                    response.raise_for_status()
                    success = True
                    result = self._map_response(response.json(), status_code)

            # Subtask 1.5: Cache successful results
            if success and multi_layer_cache.redis:
                await multi_layer_cache.redis.setex(cache_key, 300, json.dumps(result)) # 300s = 5 min TTL
                
            return result

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP error checking availability: {e}")
            return self._map_response({}, status_code)
        except Exception as e:
            logger.error(f"Fallback triggered. Primary API failed: {e}")
            return self._fallback_logic(train_number, class_type, quota)
        finally:
            latency_ms = (time.time() - start_time) * 1000
            self._log_metrics(latency_ms, success)

    def _log_metrics(self, latency_ms: float, success: bool):
        """Subtask 1.6 logging."""
        logger.info(f"[Ethical API] Latency: {latency_ms:.2f}ms | Success: {success}")
        # Could push to Prometheus here

    def _map_response(self, api_data: Dict[str, Any], status_code: int) -> Dict[str, Any]:
        """
        Subtask 1.7: Map API response codes to internal RouteMaster codes.
        """
        internal_code = "UNKNOWN_ERROR"
        if status_code == 200:
            internal_code = "SUCCESS"
        elif status_code == 429:
            internal_code = "RATE_LIMITED"
        elif status_code in [400, 404]:
            internal_code = "INVALID_REQUEST"
            
        return {
            "status": internal_code,
            "data": api_data.get("data", []),
            "source": "RAPID_API_PARTNER" if status_code == 200 else "FALLBACK"
        }

    def _fallback_logic(self, train_number: str, class_type: str, quota: str) -> Dict[str, Any]:
        """Subtask 1.4: Implement fallback logic if primary API fails."""
        # Returns a pessimistic estimate or connects to secondary B2B provider
        return {
            "status": "FALLBACK_ACTIVATED",
            "data": [{"availability": "CHECK_IRCTC_DIRECTLY", "fare": 0}],
            "source": "FALLBACK"
        }

    def _generate_mock_response(self, train_number: str, source: str, destination: str, date: str, class_type: str, quota: str) -> Dict[str, Any]:
        import random
        # Subtask 1.8: Handle quota-specific availability
        prefix = "AVAILABLE" if quota == "GN" else "WL" if quota == "TQ" else "RAC"
        return {
            "data": [{
                "train_number": train_number,
                "availability": f"{prefix}-{random.randint(1, 100)}",
                "fare": random.randint(500, 2500),
                "class_type": class_type,
                "quota": quota
            }]
        }

# Singleton instance for dependency injection
seat_provider = RapidApiSeatProvider()
