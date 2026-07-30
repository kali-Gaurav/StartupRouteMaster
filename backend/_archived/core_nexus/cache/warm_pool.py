import logging
import random
from typing import Optional
from .mmap_cortex import nexus_cortex

logger = logging.getLogger("nexus.cache.warm_pool")

class SessionWarmPool:
    """
    [Task 46] Global Session Warming Pool.
    Shared memory-mapped session sharing to reduce login delays.
    """
    
    def put_session(self, cookie_data: str):
        """Add a freshly warmed session to the pool."""
        slot = random.randint(0, 9)
        nexus_cortex.write_session(slot, cookie_data)
        # logger.info(f"🍪 [WARM_POOL] Stored warm session in Slot {slot}")

    def get_any_session(self) -> Optional[str]:
        """Grab any available warm session."""
        slots = list(range(10))
        random.shuffle(slots)
        
        for slot in slots:
             session = nexus_cortex.get_session(slot)
             if session:
                  # logger.info(f"🍪 [WARM_POOL] Leasing session from Slot {slot}")
                  return session
        return None

session_warm_pool = SessionWarmPool()
