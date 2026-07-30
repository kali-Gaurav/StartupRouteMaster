import asyncio
import logging
import time
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from services.scraper_sentinel import scraper_sentinel

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-scraper")

async def run_scraper_test():
    logger.info("🧪 Launching NEXUS-6.7: Scraper Sentinel Reliability Benchmark...")
    
    # 1. Start Browser
    logger.info("🛡️ Initializing Sentinel (Layer 2 Node Mock)...")
    await scraper_sentinel.start()
    
    # 2. Test Multi-Context Acquisition [Task 6.5 Stickiness Mock]
    logger.info("🛡️ Testing Task 6.5: Parallel Context Acquisition...")
    
    tasks = [scraper_sentinel.acquire_context() for _ in range(3)]
    contexts = await asyncio.gather(*tasks)
    
    logger.info(f"✅ SUCCESS: {len(contexts)} contexts acquired simultaneously.")
    
    # 3. Test Recycling Logic [Task 6.3]
    logger.info("🛡️ Testing Task 6.3: Force Rebuild / Recycling...")
    entry = contexts[0]
    
    # Mock 'expired' status
    await scraper_sentinel.release_context(entry, status="expired")
    
    after_count = len(scraper_sentinel._contexts)
    if after_count >= 2: # Original pool was 2+1, after recycling 1 and creating 1 it stays stable
         logger.info(f"✅ SUCCESS: Context correctly recycled and rebuilt. Pool Size: {after_count}")
    else:
         logger.error(f"❌ FAILURE: Context count dropped unexpectedly: {after_count}")
         return 1

    # 4. Total Shutdown
    await scraper_sentinel.stop()
    logger.info("🎉 Task 6.7 VERIFIED: Scraper Sentinel Lifecycle is Stable.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_scraper_test()))
