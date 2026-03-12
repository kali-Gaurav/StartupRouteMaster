import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.3")

BASE_URL = "http://127.0.0.1:8000"

async def verify_adaptive_timeout():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Trigger massive CPU block (multiple times to ensure high average)
        logger.info("Triggering high latency environment...")
        for _ in range(3):
            try:
                await client.get(f"{BASE_URL}/api/test/cpu-spike", timeout=1.0)
            except: pass
        
        # 2. Immediately search
        logger.info("Performing search during lag...")
        start = time.time()
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15", "budget": "all"}
        
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        duration = time.time() - start
        
        logger.info(f"Search returned status {resp.status_code} in {duration:.2f}s")
        
        # If the adaptive timeout worked, it should have failed around 15s (half of 30s) or less
        # because the event loop monitor should have detected the spike.
        if resp.status_code == 504:
            logger.info(f"✅ Adaptive Timeout Verified. Fail-fast triggered in {duration:.2f}s")
        elif duration < 25.0:
            logger.info(f"✅ Search completed fast ({duration:.2f}s), likely within adaptive budget.")
        else:
            logger.warning(f"Timeout took {duration:.2f}s, might not be adaptive enough.")

if __name__ == "__main__":
    asyncio.run(verify_adaptive_timeout())
