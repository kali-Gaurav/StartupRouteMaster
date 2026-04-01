import logging
import asyncio
import gc
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database.session import initialize_database_pools, _dispose_all_pools
from services.multi_layer_cache import multi_layer_cache
from services.scraper_sentinel import scraper_sentinel
from services.storage_sync import r2_sync_manager
from core.container import container
from utils.http_client import HttpClientManager
from core.nexus.bootstrapper import nexus_boot
from core.nexus.node import NexusNode

logger = logging.getLogger("nexus.lifespan")

# [Task 1.2] Custom Node Wrapper for existing providers
class GlobalServiceNode(NexusNode):
    def __init__(self, name: str, start_fn, stop_fn, critical=True, dependencies=None):
        super().__init__(name, critical=critical, dependencies=dependencies)
        self.start_fn = start_fn
        self.stop_fn = stop_fn
        
    async def on_start(self):
        await self.start_fn()
        
    async def on_stop(self):
        await self.stop_fn()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    [Task 1.4-6] Nexus V3 Deterministic Lifespan.
    Manages the 'Nexus Fiber' deterministic boot sequence and atomic halt protocol.
    """
    # 1. Aggressive GC Tuning for VPS [Task 41]
    gc.set_threshold(400, 5, 5)
    
    # [Task 1.3 & 1.10] Layer 1: Security Perimeter (P0)
    from core.nexus.security.node import security_node
    nexus_boot.register(security_node)

    # [Task 5.1 & 10.1] Layer 2: Performance & Data Fabric
    from core.nexus.cache.node import cache_node
    from core.nexus.database.node import database_node
    nexus_boot.register(cache_node)
    nexus_boot.register(database_node)
    
    # [Task 4.2 & 6.2] Layer 3: Integrity & Discovery
    from core.nexus.financial.node import financial_node
    # from core.nexus.scraper.node import scraper_node
    nexus_boot.register(financial_node)
    
    # [Task 7.10] Layer 4: Intelligence & Optimizer
    from core.nexus.rl.node import rl_node
    nexus_boot.register(rl_node)
    
    # [Task 8.10 & 9.10] Layer 5: Search & Real-time Graph
    from core.nexus.search.node import search_node
    from core.nexus.transit.reconciler import transit_node
    nexus_boot.register(search_node)
    nexus_boot.register(transit_node)

    # 2. 🚀 [NEXUS DETERMINISTIC BOOT] Task 1.4 & 10.1
    logger.info("🚀 [NEXUS] Initiating Deterministic Core Bootstrap (V3-Fiber Protocol)...")
    
    # [Task 126 Alignment] Production R2 Sync Pull: 
    # Ephemeral VPS (Railway) starts with clean state; must pull DB from R2.
    from database.config import Config
    if Config.ENVIRONMENT == "production":
        skip_sync = os.getenv("SKIP_BOOT_SYNC", "false").lower() == "true"
        if not skip_sync:
            logger.info("📦 [NEXUS:PRODUCTION] Pulling persistent data from Cloudflare R2...")
            try:
                # Synchronize databases before starting the core nodes
                await r2_sync_manager.full_sync_down()
                logger.info("✅ [NEXUS] R2 Synchronization Complete.")
            except Exception as e:
                logger.warning(f"⚠️ [NEXUS] R2 Sync-Down failed. Booting with local/fallback state: {e}")
        else:
            logger.info("⏩ [NEXUS] SKIP_BOOT_SYNC is active. Skipping R2 Pull.")

    success = await nexus_boot.bootstrap()
    
    if not success:
        logger.critical("🛑 [NEXUS] MASTER BOOT FAILED. Entering SAFE_MODE.")
        # Optional: Force some standby states to keep API alive during DEGRADED mode
    else:
        logger.info(f"✅ [NEXUS] Operational Readiness: {nexus_boot.state.value} (Fiber Spine Active).")
        
        # [Task 151] Start Smart Search Pre-Warmer (Background)
        from services.search_prewarmer import search_prewarmer
        asyncio.create_task(search_prewarmer.start_background_loop())
        logger.info("🌤️ [NEXUS:DASHBOARD] Smart Search Pre-Warmer online (Background).")
        
    yield
    
    # 3. --- ATOMIC SHUTDOWN PROTOCOL (Task 1.6) ---
    logger.warning("🔌 [NEXUS] SIGTERM/System Stop detected. Initiating Halt Sequence...")
    
    try:
        # [Task 1.6] Reverse-Order Halt: Search -> Scraper -> DB -> Cache
        await nexus_boot.halt()
        
        # Cleanup remaining global systems
        await r2_sync_manager.full_sync_up()
        await container.shutdown_all()
        await HttpClientManager.close_session()
        
    except Exception as e:
        logger.error(f"⚠️ [NEXUS] Shutdown Halt Error: {e}")
        
    gc.collect()
    # Final Log Flush
    for handler in logging.getLogger().handlers:
        handler.flush()
    logger.info("🛑 [NEXUS] System-Wide Shutdown complete. Fiber Dismantled.")
