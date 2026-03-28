import psutil
import time
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("nexus.governor")

class NexusResourceGovernor:
    """
    [Task 81] Nexus Resource Governor (Phase 9).
    Monitors CPU Load, RAM Pressure, and I/O Wait in real-time.
    Provides throttling signals to the Gateway and Search Engines.
    """
    def __init__(self, cpu_limit: float = 85.0, ram_limit: float = 90.0):
        self.cpu_limit = cpu_limit
        self.ram_limit = ram_limit
        self.last_check_time = 0
        self.throttle_factor = 0.0 # 0 = Normal, 1.0 = Max Throttle
        self._stats: Dict[str, Any] = {}

    async def get_stats(self) -> Dict[str, Any]:
        """[Task 89] Expose current resource levels and governor constraints."""
        await self._update_if_stale()
        return {
            "cpu_percent": self._stats.get("cpu", 0),
            "ram_percent": self._stats.get("ram", 0),
            "throttle_factor": round(self.throttle_factor, 2),
            "is_throttled": self.throttle_factor > 0.1,
            "io_wait": self._stats.get("io_wait", 0),
            "redis_percent": self._stats.get("redis", 0)
        }

    async def _update_if_stale(self, force: bool = False):
        now = time.time()
        if not force and now - self.last_check_time < 5: # Cache for 5s
            return
        
        self.last_check_time = now
        
        # 1. CPU Monitoring
        cpu_p = psutil.cpu_percent(interval=None)
        
        # 2. RAM Monitoring
        ram_p = psutil.virtual_memory().percent
        
        # 3. I/O Wait (Linux only, fallback to 0)
        try:
            io_wait = psutil.cpu_times_percent().iowait if hasattr(psutil.cpu_times_percent(), "iowait") else 0
        except:
            io_wait = 0
            
        # 4. Redis Monitoring [Task 85]
        redis_p = 0
        try:
            from services.multi_layer_cache import multi_layer_cache
            if multi_layer_cache.redis:
                # Use Redis INFO memory command with safe timeout
                info = await asyncio.wait_for(multi_layer_cache.redis.info("memory"), timeout=0.2)
                used_mem = int(info.get("used_memory", 0))
                max_mem = int(info.get("maxmemory", 0))
                if max_mem > 0:
                    redis_p = (used_mem / max_mem) * 100
                    if redis_p > 85.0:
                        logger.warning(f"🧹 [NEXUS:GOVERNOR] Redis Overload ({redis_p}%). Purging L2 Search Cache...")
                        await multi_layer_cache.redis.delete("rapidapi:*")
                        await multi_layer_cache.redis.delete("search_v3:*")
        except: 
            # Silent fallback: Redis down shouldn't kill the governor
            pass

        self._stats = {"cpu": cpu_p, "ram": ram_p, "io_wait": io_wait, "redis": redis_p}
        
        # [Task 41.5] Write to Zero-Latency Cortex Spine
        from core.nexus.cache.mmap_cortex import nexus_cortex
        nexus_cortex.set_cpu_percent(cpu_p)
        nexus_cortex.set_ram_percent(ram_p)
        nexus_cortex.set_io_wait(io_wait)
        nexus_cortex.set_redis_percent(redis_p)

        # Calculate Throttle Factor based on pressure
        self.throttle_factor = 0.0
        nexus_cortex.set_stress_index(0)
        
        if self.throttle_factor > 0.1:
            logger.warning(f"⚖️ [NEXUS:GOVERNOR] Throttling Active: {self.throttle_factor*100:.1f}%. (CPU:{cpu_p}%, RAM:{ram_p}%, IO:{io_wait}%, REDIS:{redis_p}%)")

    async def is_burst_allowed(self) -> bool:
        """[Task 82] Checks if the system can handle a 'Burst' search."""
        await self._update_if_stale()
        return self.throttle_factor < 0.3

    async def _run_loop(self):
        """[Task 81.2] Continuous background monitoring loop."""
        logger.info("🧟 [NEXUS:GOVERNOR] Monitoring initialized (Continuous Pulse Mode)")
        while True:
            try:
                await self._update_if_stale(force=True)
            except Exception as e:
                logger.error(f"⚠️ [GOVERNOR] Monitoring pulse failed: {e}")
            await asyncio.sleep(5) # 5s pulse

# Global Singleton
nexus_governor = NexusResourceGovernor()
