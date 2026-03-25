
import asyncio
import logging
import sys
import os
from datetime import datetime, date

# Add project root and backend to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyFixes")

async def verify():
    logger.info("--- Verifying Phase 1 Fixes ---")
    
    try:
        logger.info("1. Importing TurboRouter...")
        from backend.core.route_engine.turbo_router import TurboRouter
        tr = TurboRouter()
        logger.info("   TurboRouter instantiated.")
    except Exception as e:
        logger.error(f"❌ TurboRouter Failed: {e}")
        return

    try:
        logger.info("2. Importing UltraTurbo...")
        from backend.core.route_engine.ultra_turbo import UltraTurboDirectEngine
        ut = UltraTurboDirectEngine()
        logger.info("   UltraTurbo instantiated.")
    except Exception as e:
        logger.error(f"❌ UltraTurbo Failed: {e}")
        return

    try:
        logger.info("3. Importing Orchestrator...")
        # Mock engine instance
        class MockEngine:
            pass
        from backend.core.route_engine.orchestrator import UnifiedRoutingOrchestrator
        orch = UnifiedRoutingOrchestrator(MockEngine())
        logger.info("   Orchestrator instantiated.")
    except Exception as e:
        logger.error(f"❌ Orchestrator Failed: {e}")
        return

    try:
        logger.info("4. Importing Graph & MemMap...")
        from backend.core.route_engine.graph import MemMapManager, RealtimeOverlay
        ro = RealtimeOverlay()
        logger.info("   RealtimeOverlay instantiated.")
        
        # Test GC logic safely
        import numpy as np
        arr = np.zeros((10,), dtype=np.int32)
        path = MemMapManager.save_array("test_gc_verify", arr)
        logger.info(f"   MemMap saved to {path}")
        
    except Exception as e:
        logger.error(f"❌ Graph/MemMap Failed: {e}")
        return

    logger.info("✅ All modules imported and instantiated successfully.")

if __name__ == "__main__":
    try:
        # Check if we have an event loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(verify())
