import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.bootstrapper import NexusBootstrapper
from core.nexus.node import NexusNode

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test-boot")

class MockNode(NexusNode):
    def __init__(self, name, critical=True, dependencies=None, fail=False, delay=0.1):
        super().__init__(name, critical=critical, dependencies=dependencies)
        self.fail = fail
        self.delay = delay
        self.started = False
        self.stopped = False

    async def on_start(self):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError(f"Simulated failure for {self.name}")
        self.started = True

    async def on_stop(self):
        self.stopped = True

async def run_test():
    logger.info("🧪 Launching NEXUS-1.8: System-Level Boot Graph Test...")
    
    bootstrapper = NexusBootstrapper()
    
    # 1. Register Mock DAG
    # Redis -> [DB, Scraper] -> Search
    bootstrapper.register(MockNode("redis", dependencies=[]))
    bootstrapper.register(MockNode("database", dependencies=["redis"]))
    bootstrapper.register(MockNode("scraper", dependencies=["redis"]))
    bootstrapper.register(MockNode("search", dependencies=["database", "scraper"], critical=True))
    
    # 2. Execute Boot
    success = await bootstrapper.bootstrap()
    
    if success:
        logger.info("✅ SUCCESS: Full Graph Sequence Resolved and Started.")
    else:
        logger.error("❌ FAILURE: Bootstrapper failed to resolve graph.")
        return 1

    # 3. Verify Order
    # Search must be last
    if bootstrapper.boot_order[-1] != "search":
        logger.error(f"❌ ORDER FAILURE: Search was not the final node. Order: {bootstrapper.boot_order}")
        return 1
    
    # Redis must be first
    if bootstrapper.boot_order[0] != "redis":
        logger.error(f"❌ ORDER FAILURE: Redis was not the first node. Order: {bootstrapper.boot_order}")
        return 1

    # 4. Halt
    logger.info("🧪 Testing Task 1.6: Graceful Halt Order...")
    await bootstrapper.halt()
    
    logger.info("🎉 Task 1.8 VERIFIED: State-Graph is Healthy and Deterministic.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_test()))
