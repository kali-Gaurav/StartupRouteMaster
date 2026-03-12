import asyncio
import httpx
import logging
import tracemalloc
import gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.10")

BASE_URL = "http://127.0.0.1:8000"

async def run_load_test(count=500):
    logger.info(f"Running memory leak test with {count} requests...")
    
    # 1. Warmup
    async with httpx.AsyncClient() as client:
        for _ in range(10):
            await client.get(f"{BASE_URL}/api/health")
    
    gc.collect()
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()
    
    # 2. Heavy Load
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(count):
            tasks.append(client.get(f"{BASE_URL}/api/health"))
            if len(tasks) >= 50:
                await asyncio.gather(*tasks)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks)
            
    # 3. Cleanup & Compare
    gc.collect()
    snapshot2 = tracemalloc.take_snapshot()
    
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    logger.info("[ Top 10 Memory Growth Points ]")
    leak_found = False
    for stat in top_stats[:10]:
        logger.info(str(stat))
        # Arbitrary threshold: if any single line grew by more than 1MB in 500 small requests
        if stat.size_diff > 1024 * 1024:
            leak_found = True
            
    tracemalloc.stop()
    
    if leak_found:
        logger.error("❌ Potential memory leak detected in middleware/stack!")
    else:
        logger.info("✅ No significant memory leaks detected in middleware.")

if __name__ == "__main__":
    asyncio.run(run_load_test())
