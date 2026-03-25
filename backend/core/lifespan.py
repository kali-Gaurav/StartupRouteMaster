import logging
import asyncio
import gc
from contextlib import asynccontextmanager
from fastapi import FastAPI

from services.storage_sync import r2_sync_manager
from core.container import container

logger = logging.getLogger("routemaster.lifespan")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    [Task 1 & 5] Nexus V3 Deterministic Lifespan.
    Manages the 'Nexus Fiber' bootstrapper and halt protocols.
    """
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.services.ledger import nexus_ledger
    
    # 1. Aggressive GC Tuning for VPS [Task 41]
    gc.set_threshold(400, 5, 5)
    
    # 2. Register core nodes (Task 1-5)
    nexus_boot.register(nexus_ledger)
    # Note: Database and Redis nodes will be registered here as separate NexusNodes
    
    # 3. 🚀 [NEXUS DETERMINISTIC BOOT] Task 1.3
    logger.info("🚀 [NEXUS] Initiating Deterministic Core Bootstrap (V3 Protocol)...")
    success = await nexus_boot.bootstrap()
    
    if not success:
        logger.critical("🛑 [NEXUS] MASTER BOOT FAILED. System entering SAFE_MODE.")
        # We continue to let the app start so we can serve 503/errors via Gatekeeper
    else:
        logger.info("✅ [NEXUS] Operational Readiness Achieved.")

    yield
    
    # --- GRACEFUL SHUTDOWN (Task 5) ---
    logger.warning("🔌 [NEXUS] SIGTERM/System Stop detected. Initiating Halt Protocol...")
    
    # [Task 5.2] Execute Node Teardowns in reverse dependency order
    await nexus_boot.halt()
    
    # Cleanup remaining legacy systems
    try:
        await r2_sync_manager.full_sync_up()
        await container.shutdown_all()
        from utils.http_client import HttpClientManager
        await HttpClientManager.close_session()
    except Exception as e:
        logger.warning(f"Shutdown cleanup error: {e}")
        
    gc.collect()
    # [Task 13.1] Final Log Flush
    for handler in logging.getLogger().handlers:
        handler.flush()
    logger.info("🛑 [NEXUS] System-Wide Shutdown complete. Registry saved.")
