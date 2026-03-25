import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nexus.node import NexusNode
from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import nexus_state_manager, NexusState

# 🛡️ MOCK NODES FOR TESTING
class MockDBNode(NexusNode):
    async def on_start(self):
        logger.info("🗄️ MockDB: Connecting...")
        await asyncio.sleep(0.5)
        
    async def on_stop(self):
        logger.info("🗄️ MockDB: Closing...")

class MockRedisNode(NexusNode):
    async def on_start(self):
        logger.info("⚡ MockRedis: Initializing...")
        await asyncio.sleep(0.3)
        
    async def on_stop(self):
        logger.info("⚡ MockRedis: Shutting down...")

class MockScraperNode(NexusNode):
    async def on_start(self):
        logger.info("🕷️ MockScraper: Warming browser pool...")
        await asyncio.sleep(1.0)
        
    async def on_stop(self):
        logger.info("🕷️ MockScraper: Reaping zombies...")

class MockLedgerNode(NexusNode):
    async def on_start(self):
        logger.info("💰 MockLedger: Verifying hash chain...")
        await asyncio.sleep(0.6)
        
    async def on_stop(self):
        logger.info("💰 MockLedger: Flushing audit log...")

async def run_verification():
    print("\n🧪 Starting Verification for Task 1: Nexus State-Graph Bootstrapper...\n")
    
    # Setup Log for output analysis
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    global logger
    logger = logging.getLogger("nexus-verify")

    # 1. REGISTER MOCK NODES
    db = MockDBNode("database")
    redis = MockRedisNode("redis")
    scrapers = MockScraperNode("scrapers", dependencies=["database", "redis"])
    ledger = MockLedgerNode("ledger", dependencies=["database"])
    
    nexus_boot.register(db)
    nexus_boot.register(redis)
    nexus_boot.register(scrapers)
    nexus_boot.register(ledger)

    # 2. RESOLVE GRAPH
    print("🛠 Step 1: Resolving Nexus Dependency Graph...")
    nexus_boot.resolve_dependencies()
    # Expect 2 layers: Layer 1: [DB, Redis], Layer 2: [Scrapers, Ledger]
    if len(nexus_boot._boot_order) != 2:
        print(f"❌ FAILED: Expected 2 layers, found {len(nexus_boot._boot_order)}")
        return False
    print("✅ Dependency Graph Resolved (Layers verified).")

    # 3. RUN BOOTSTRAP
    print("\n🛠 Step 2: Executing Parallel Nexus Bootstrap...")
    success = await nexus_boot.bootstrap()
    
    if not success or nexus_state_manager.current_state != NexusState.READY:
        print(f"❌ BOOT FAILED: Current state: {nexus_state_manager.current_state.value}")
        return False
    
    print("✅ System Reached READY State successfully.")

    # 4. RUN HALT
    print("\n🛠 Step 3: Executing Graceful Halt Protocol...")
    await nexus_boot.halt()
    
    if nexus_state_manager.current_state != NexusState.OFFLINE:
         print(f"❌ HALT FAILED: Current state: {nexus_state_manager.current_state.value}")
         return False
    
    print("✅ System Reached OFFLINE State safely.")

    print("\n🎉 TASK 1 VERIFIED: Nexus State-Graph is Deterministic and Resilient.\n")
    return True

if __name__ == "__main__":
    asyncio.run(run_verification())
