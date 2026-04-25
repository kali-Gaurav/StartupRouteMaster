import multiprocessing
import os
import logging
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any, List
from core.route_engine.base import RoutingRequest, RoutingResponse

logger = logging.getLogger("nexus.spine")

class NeuralSpine:
    """
    [Point 14 & 17] Nexus Neural Spine: High-Performance Multi-Process Sharding.
    Dedicated to KVM 2 (2 Cores / 8GB RAM).
    """
    _executor: ProcessPoolExecutor = None
    _shared_graph = None

    @classmethod
    def initialize(cls):
        """
        [KVM 2 Optimization] Initialize compute shards.
        We reserve 1 core for API/Light and 1 core for Heavy Search.
        """
        if cls._executor is not None:
            return
            
        # Pinning to max_workers=1 for the 'Heavy' compute shard
        # This prevents CPU thrashing on a 2-core VPS.
        cls._executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context('spawn')
        )
        logger.info(f"🧠 [NEXUS:SPINE] Neural Spine Active | Worker Shard: 1 | PID: {os.getpid()}")

    @classmethod
    async def dispatch_calculate(cls, engine, request: RoutingRequest) -> RoutingResponse:
        """
        [Zero-Block Dispatching] Offloads heavy CPU calculation to a background process.
        Includes [Point 9] Advanced Self-Healing for Disaster Resilience.
        """
        if cls._executor is None:
            logger.warning("🔄 [NEXUS:SPINE] Shard Missing. Re-initializing for recovery...")
            cls.initialize()

        # [Point 28] Zero-Copy Optimization Check
        from core.nexus.shm_bridge import SharedMemoryBridge
        bridge = SharedMemoryBridge.get_instance()
        
        # [Chaos Drill: SHM_POISON] - If segment unlinked, fallback enabled
        shm_ready = bridge.get_data_view() is not None
        request.metadata["shm_enabled"] = shm_ready

        # [Ariadne Self-Healing Pipeline]
        retries = 2
        while retries > 0:
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    cls._executor,
                    cls._perform_headless_search,
                    engine,
                    request
                )
            except Exception as e:
                retries -= 1
                logger.error(f"🚨 [NEXUS:SPINE] Shard Failure: {e}. Retries left: {retries}")
                # [Point 14] Immediate Recovery: Wipe and Respawn
                cls._executor = None
                cls.initialize()
                
                if retries == 0:
                    logger.critical("💀 [NEXUS:SPINE] Healing Failed. Falling back to Core 0 (Sync).")
                    return await engine.find_routes(request)
        
        raise RuntimeError("Spine Dispatch Critical Failure")

    @staticmethod
    def _perform_headless_search(engine, request: RoutingRequest) -> RoutingResponse:
        """
        Synchronous worker function running in the background shard.
        """
        try:
            # [Point 28] Shared Memory Re-attachment
            from core.nexus.shm_bridge import SharedMemoryBridge
            shm_view = SharedMemoryBridge.get_instance().get_data_view()
            if shm_view and request.metadata.get("shm_enabled"):
                # We could rebuild the graph from SHM view here to avoid pickling overhead
                # For this prototype, we'll just log the success.
                pass

            import asyncio
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(engine.find_routes(request))
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            raise

def spine_dispatch(engine_type: str = "turbo"):
    """Decorator to automatically offload engine calls to the spine."""
    def decorator(func):
        async def wrapper(self, request: RoutingRequest, *args, **kwargs):
            if request.budget < 0.5 or "ultra" in engine_type.lower():
                # For high-load or 'Ultra' searches, always use the spine
                return await NeuralSpine.dispatch_calculate(self, request)
            return await func(self, request, *args, **kwargs)
        return wrapper
    return decorator
