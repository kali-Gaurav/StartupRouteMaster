import logging
import asyncio
from core.nexus.node import NexusNode
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("nexus.cache")

class CacheFabricNode(NexusNode):
    """[Task 5.1 & 8.3] Cache Fabric Node (Layer 2)."""
    
    def __init__(self, name: str = "cache", critical: bool = True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies if dependencies else ["security"])
        
    async def on_start(self):
        """[Task 5.1] Initialize Multi-Layer Cache with Health Latch."""
        logger.info("[NEXUS:CACHE] Activating Memory Fabric (Layer 2)...")
        await multi_layer_cache.init()
        # [Task 81] Unified Nexus Resource Governor (Phase 9)
        from core.nexus.audit.governor import nexus_governor
        # Start the background monitoring task
        self._governor_task = asyncio.create_task(nexus_governor._run_loop())
        
        if multi_layer_cache.health_latch:
             logger.info("[NEXUS:CACHE] Zero-Latency Health Latch: ACTIVE.")
        else:
             logger.warning("[NEXUS:CACHE] Cache Fabric in Degraded Mode.")
        
    async def on_stop(self):
        """Final flush of L1 memory cache."""
        logger.info("[NEXUS:CACHE] Halting Cache Fabric.")
        await multi_layer_cache.shutdown()

cache_node = CacheFabricNode()
