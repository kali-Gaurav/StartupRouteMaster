import multiprocessing
import time
import os
import logging
from core.nexus.cache.mmap_cortex import NexusMmapCortex, BIT_MASTER_KILL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test.cortex")

def worker_process():
    """Continuously check the kill switch status."""
    # We use a fresh instance in the sub-process
    cortex = NexusMmapCortex()
    logger.info("👷 Worker: Neural Spine Mapped.")
    
    start_time = time.time()
    while time.time() - start_time < 5:
        if cortex.is_kill_switch_active():
            logger.warning("👷 Worker: Detected KILL SWITCH! Exit.")
            return
        time.sleep(0.1)
    logger.info("👷 Worker: Finished gracefully.")

def test_inter_process_cortex():
    logger.info("🧪 Starting P5.41 IP-Cortex Test...")
    
    # 1. Master instance (Initializes file)
    master_cortex = NexusMmapCortex()
    master_cortex.set_bit(0, BIT_MASTER_KILL, False) # Ensure clean start
    
    # 2. Start Worker
    p = multiprocessing.Process(target=worker_process)
    p.start()
    
    time.sleep(1)
    
    # 3. Master flips the bit
    logger.info("🛡️ Master: Flipping KILL SWITCH bit...")
    master_cortex.set_bit(0, BIT_MASTER_KILL, True)
    
    p.join(timeout=2)
    if p.is_alive():
        logger.error("❌ Test FAILED: Worker did not detect bit change in time.")
        p.terminate()
    else:
        logger.info("✅ Test PASSED: Inter-process state propagate verified (L0).")

if __name__ == "__main__":
    test_inter_process_cortex()
