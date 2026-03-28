import psutil
import asyncio
import logging
from .mmap_cortex import nexus_cortex

logger = logging.getLogger("nexus.cache.governor")

class ResourceGovernor:
    """
    [Task 42] Nexus Resource Governor.
    Monitors CPU/RAM/Vitals and updates the Mmap SSI (System Stress Index).
    Enables zero-latency load-shedding across all workers.
    """
    
    def __init__(self, interval: int = 5):
        self.interval = interval
        self._task = None

    async def calculate_ssi(self) -> int:
        """Calculate a composite 0-100 score of VPS stress."""
        try:
            cpu_load = psutil.cpu_percent(interval=None)
            ram_load = psutil.virtual_memory().percent
            
            # Simple weighted composite
            # Priority to CPU for scrapers, RAM for cache
            ssi = int((cpu_load * 0.7) + (ram_load * 0.3))
            return min(100, ssi)
        except Exception as e:
            logger.error(f"⚠️ [GOVERNOR] Metrics failure: {e}")
            return 50 # Fail-safe middle ground

    async def run_forever(self):
        """Main loop for the Governor background task."""
        logger.info(f"🧟 [GOVERNOR] Monitoring initialized (Interval: {self.interval}s)")
        while True:
            ssi = await self.calculate_ssi()
            nexus_cortex.set_stress_index(ssi)
            
            if ssi > 85:
                 logger.warning(f"🔥 [GOVERNOR] CRITICAL STRESS: {ssi}% - Load-Shedding Active.")
            elif ssi > 70:
                 logger.info(f"⚠️ [GOVERNOR] High Load: {ssi}%")
                 
            await asyncio.sleep(self.interval)

    def start(self):
        self._task = asyncio.create_task(self.run_forever())

resource_governor = ResourceGovernor()
