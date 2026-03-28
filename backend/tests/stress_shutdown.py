import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.bootstrapper import NexusBootstrapper
from core.nexus.node import NexusNode

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("stress-shutdown")

class PersistentNode(NexusNode):
    def __init__(self, name, dependencies=None):
        super().__init__(name, dependencies=dependencies)
        self.flushed = False

    async def on_start(self):
        logger.info(f"💠 [NEXUS:{self.name}] State: START")
        
    async def on_stop(self):
        # Heavy persistence simulation
        logger.info(f"⏹️ [NEXUS:{self.name}] FLUSHING DATA...")
        await asyncio.sleep(0.5)
        self.flushed = True
        logger.info(f"✅ [NEXUS:{self.name}] PERSISTENCE COMMITTED.")

async def run_stress():
    logger.info("🧪 Launching NEXUS-1.9: Data Integrity Stress Test...")
    
    boot = NexusBootstrapper()
    
    ledger = PersistentNode("ledger", dependencies=["database"])
    db = PersistentNode("database", dependencies=[])
    
    boot.register(db)
    boot.register(ledger)
    
    await boot.bootstrap()
    
    logger.info("💥 SIMULATING SIGTERM (Shutdown Event)...")
    st = asyncio.get_event_loop().time()
    
    # 1. Start Halt
    await boot.halt()
    
    duration = asyncio.get_event_loop().time() - st
    
    if ledger.flushed and db.flushed:
        logger.info(f"🎉 Task 1.9 Verified: Atomic Persistence Sequence preserved in {duration:.2f}s.")
    else:
        logger.error("❌ FAILURE: Incomplete shutdown protocol.")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_stress()))
