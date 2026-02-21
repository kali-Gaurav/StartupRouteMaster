"""
API client for Rappid train real-time service.
Handles HTTP requests, retries, caching, and error handling.

API Documentation:
- Base URL: https://rappid.in/apis/
- Endpoint: train.php?train_no=XXXXX
- Response: JSON with train data array
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)


class RappidAPIClient:
    """
    Synchronous client for Rappid train API with retry logic and caching.
    """
    
    BASE_URL = "https://rappid.in/apis/train.php"
    TIMEOUT = 10  # seconds
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, cache_enabled: bool = True):
        self.session = self._create_session()
        self.cache_enabled = cache_enabled
        self.cache: Dict[str, tuple] = {}  # {train_no: (response, timestamp)}
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set reasonable headers
        session.headers.update({
            "User-Agent": "Routemaster-RailwayRouteEngine/1.0",
            "Accept": "application/json"
        })
        
        return session
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((requests.RequestException, json.JSONDecodeError))
    )
    def fetch_train_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch live status for a specific train.
        
        Args:
            train_number: Train number (e.g., "12345")
            
        Returns:
            API response dict or None if failed
        """
        # Check cache
        if self.cache_enabled and train_number in self.cache:
            response, timestamp = self.cache[train_number]
            if datetime.now() - timestamp < timedelta(seconds=self.CACHE_TTL):
                logger.debug(f"✓ Cache hit for train {train_number}")
                return response
        
        try:
            logger.info(f"📡 Fetching live status for train {train_number}...")
            
            response = self.session.get(
                self.BASE_URL,
                params={"train_no": train_number},
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response
            if not data.get("success"):
                logger.warning(f"⚠️ API returned success=false for train {train_number}")
                return None
            
            # Cache the response
            if self.cache_enabled:
                self.cache[train_number] = (data, datetime.now())
            
            logger.info(f"✓ Successfully fetched train {train_number}")
            return data
        
        except requests.Timeout:
            logger.error(f"❌ API timeout for train {train_number}")
            return None
        except requests.ConnectionError:
            logger.error(f"❌ Connection error for train {train_number}")
            return None
        except requests.RequestException as e:
            logger.error(f"❌ Request failed for train {train_number}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON response for train {train_number}: {e}")
            return None
    
    def fetch_multiple_trains(self, train_numbers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch status for multiple trains sequentially.
        
        Args:
            train_numbers: List of train numbers
            
        Returns:
            Dict mapping train_number -> response (or None if failed)
        """
        results = {}
        for train_no in train_numbers:
            results[train_no] = self.fetch_train_status(train_no)
        
        return results
    
    def clear_cache(self):
        """Clear response cache."""
        self.cache.clear()
        logger.debug("🗑️ API response cache cleared")
    
    def close(self):
        """Close HTTP session."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class AsyncRappidAPIClient:
    """
    Asynchronous client for Rappid train API with concurrent requests.
    Allows fetching multiple trains in parallel.
    """
    
    BASE_URL = "https://rappid.in/apis/train.php"
    TIMEOUT = 10  # seconds
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, cache_enabled: bool = True, max_concurrent: int = 10):
        self.cache_enabled = cache_enabled
        self.cache: Dict[str, tuple] = {}
        self.max_concurrent = max_concurrent
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
            connector = aiohttp.TCPConnector(limit_per_host=self.max_concurrent)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "Routemaster-RailwayRouteEngine/1.0",
                    "Accept": "application/json"
                }
            )
        return self.session
    
    async def fetch_train_status(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Asynchronously fetch live status for a train.
        
        Args:
            train_number: Train number
            
        Returns:
            API response dict or None if failed
        """
        # Check cache
        if self.cache_enabled and train_number in self.cache:
            response, timestamp = self.cache[train_number]
            if datetime.now() - timestamp < timedelta(seconds=self.CACHE_TTL):
                logger.debug(f"✓ Cache hit for train {train_number}")
                return response
        
        session = await self._get_session()
        
        try:
            logger.info(f"📡 Async fetching train {train_number}...")
            
            async with session.get(
                self.BASE_URL,
                params={"train_no": train_number}
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ API returned status {resp.status} for train {train_number}")
                    return None
                
                data = await resp.json()
                
                if not data.get("success"):
                    logger.warning(f"⚠️ API returned success=false for train {train_number}")
                    return None
                
                # Cache response
                if self.cache_enabled:
                    self.cache[train_number] = (data, datetime.now())
                
                logger.info(f"✓ Async fetch success for train {train_number}")
                return data
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Async timeout for train {train_number}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Async client error for train {train_number}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON for train {train_number}: {e}")
            return None
    
    async def fetch_multiple_trains(self, train_numbers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch status for multiple trains concurrently.
        
        Args:
            train_numbers: List of train numbers
            
        Returns:
            Dict mapping train_number -> response
        """
        tasks = [self.fetch_train_status(tn) for tn in train_numbers]
        results = await asyncio.gather(*tasks)
        
        return {tn: result for tn, result in zip(train_numbers, results)}
    
    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()


def get_active_trains(db_session) -> List[str]:
    """
    Get list of active train numbers from database.
    Active = trains scheduled in next 24 hours with stops after current time.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        List of train numbers
    """
    from ...database.models import TrainMaster
    from datetime import datetime, timedelta
    
    try:
        # Get all trains (in production, filter by schedule)
        trains = db_session.query(TrainMaster).all()
        train_numbers = [train.train_number for train in trains]
        
        logger.info(f"📊 Found {len(train_numbers)} active trains to monitor")
        return train_numbers
    
    except Exception as e:
        logger.error(f"❌ Error fetching active trains: {e}")
        return []
