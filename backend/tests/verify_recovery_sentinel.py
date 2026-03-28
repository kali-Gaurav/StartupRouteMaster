import asyncio
import logging
import sys
import os
import time

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState
from core.nexus.node import NexusNode, NodeStatus

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-recovery")

class MockZombieNode(NexusNode):
    def __init__(self, name="zombie_node", critical=False):
        super().__init__(name, critical=critical)
        self.start_calls = 0
        self.stop_calls = 0

    async def on_start(self):
        self.start_calls += 1
        logger.info(f"MockZombieNode: Starting (Call {self.start_calls})...")
        # Record heartbeat
        nexus_boot.recovery.record_heartbeat(self.name)

    async def on_stop(self):
        self.stop_calls += 1
        logger.info(f"MockZombieNode: Stopping (Call {self.stop_calls})...")

async def test_auto_recovery():
    logger.info("🧪 Launching NEXUS-21.1: Auto-Recovery Sentinel Stress-Test...")
    
    # 1. Register Mock Node
    zombie = MockZombieNode()
    nexus_boot.register(zombie)
    
    # 2. Bootstrap
    logger.info("🛡️ Initiating Core Bootstrap...")
    await nexus_boot.bootstrap()
    
    if nexus_boot.state != SystemState.READY:
        logger.error(f"Boot Failed: {nexus_boot.state}")
        return 1

    # 3. SIMULATE FAILURE (Manual Status Flip)
    logger.info("💀 Simulating Node Crash (FAILED status)...")
    zombie.status = NodeStatus.FAILED
    
    # 4. Await Recovery (Sentinel checks every 60s, but we'll force a check or just wait)
    # Since we can't easily 'force' the private loop without hacks, let's just wait 
    # slightly more than the interval or reduce the interval for the test.
    nexus_boot.recovery.CHECK_INTERVAL = 2 # Speed up for test
    
    logger.info("⏳ Awaiting Sentinel Intervention...")
    await asyncio.sleep(5)
    
    if zombie.status == NodeStatus.RUNNING and zombie.start_calls > 1:
        logger.info(f"✅ SUCCESS: Sentinel detected failure and REBOOETED node (Starts: {zombie.start_calls}).")
    else:
        logger.error(f"❌ FAILURE: Sentinel remained idle. Status: {zombie.status.name}")
        await nexus_boot.halt()
        return 1

    # 5. SIMULATE ZOMBIE (Heartbeat Timeout)
    logger.info("🧟 Simulating Zombie Node (Heartbeat Timeout)...")
    # Backdate heartbeat to 10 mins ago
    nexus_boot.recovery._last_heartbeat[zombie.name] = time.time() - 600
    
    logger.info("⏳ Awaiting Sentinel Exorcism...")
    await asyncio.sleep(5)
    
    if zombie.start_calls > 2:
        logger.info(f"✅ SUCCESS: Sentinel detected zombie and FORCED restart (Starts: {zombie.start_calls}).")
    else:
        logger.error(f"❌ FAILURE: Sentinel missed the zombie. Starts: {zombie.start_calls}")
        await nexus_boot.halt()
        return 1

    logger.info("🎉 Task 21 VERIFIED: Auto-Recovery Sentinel is the Supreme Watchdog.")
    await nexus_boot.halt()
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(test_auto_recovery()))
