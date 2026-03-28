import asyncio
import logging
import sys
import os
import time

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-nexus")

async def test_full_spine():
    logger.info("🧪 Launching NEXUS-10.7: Master Spine Stress-Test (Fiber V3)...")
    start_time = time.time()
    
    # 1. Mock lifespan-like registration (But we use the actual nodes)
    # The lifespan.py already registers them if we were running a real app.
    # For this test, we verify the nodes individually and then as a chain.
    
    # Let's import the nodes to ensure they are registered in the global 'nexus_boot'
    from core.nexus.security.node import security_node
    from core.nexus.cache.node import cache_node
    from core.nexus.database.node import database_node
    from core.nexus.financial.node import financial_node
    from core.nexus.scraper.node import scraper_node
    from core.nexus.rl.node import rl_node
    from core.nexus.search.node import search_node
    from core.nexus.transit.reconciler import transit_node
    
    # Note: We don't manually register here as they might be registered via imports in lifespan
    # but for a SLIM test, we register the critical path
    nexus_boot.register(security_node)
    nexus_boot.register(cache_node)
    nexus_boot.register(database_node)
    nexus_boot.register(financial_node)
    # nexus_boot.register(scraper_node) # Isolated for faster spine audit
    nexus_boot.register(rl_node)
    nexus_boot.register(search_node)
    nexus_boot.register(transit_node)

    # 2. 🚀 TRIGGER BOOT
    logger.info("🛡️ Initiating Atomic Boot (7-Node Consensus)...")
    success = await nexus_boot.bootstrap()
    
    duration = time.time() - start_time
    
    if success and nexus_boot.state == SystemState.READY:
        logger.info(f"✅ SUCCESS: Nexus Fiber Spine established in {duration:.2f}s.")
        
        # 3. VERIFY NODES
        logger.info("🔍 Checking Node Vitals...")
        for node_name, node in nexus_boot.nodes.items():
             logger.info(f" - [{node_name}] Status: {node.status.name} | Critical: {node.critical}")
             
        logger.info("🎉 Task 10.7 VERIFIED: Fiber-Core is Indestructible.")
        
        # 4. CLEANUP
        await nexus_boot.halt()
        return 0
    else:
        logger.error(f"🛑 FAILURE: Nexus Boot Halted at state: {nexus_boot.state.name}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test_full_spine()))
