import time
from typing import Dict, Optional, Any
from database.models import Stop

class StationL1Cache:
    """
    Ultra-high performance L1 cache for Station Objects.
    Thread-safe enough for asyncio loop usage.
    Expires every 10 minutes to ensure DB sync.
    """
    def __init__(self, capacity: int = 4096):
        self.cache: Dict[str, Stop] = {}
        self.expiry: Dict[str, float] = {}
        self.capacity = capacity
        self.ttl = 600 # 10 mins

    def get(self, key: str) -> Optional[Stop]:
        if key in self.cache:
            if time.time() < self.expiry[key]:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.expiry[key]
        return None

    def set(self, key: str, value: Stop):
        if len(self.cache) >= self.capacity:
            # Simple FIFO eviction
            k = next(iter(self.cache))
            del self.cache[k]
            del self.expiry[k]
        
        self.cache[key] = value
        self.expiry[key] = time.time() + self.ttl

# Global Singleton for the process
station_l1_cache = StationL1Cache()
