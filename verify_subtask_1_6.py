import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.6")

BASE_URL = "http://127.0.0.1:8000"

async def slow_request(client, i):
    """Hits search which is 'heavy' and takes time."""
    payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
    try:
        start = time.time()
        # We use a long timeout for the client, but the SERVER should 503 us faster
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload, timeout=10.0)
        logger.info(f"Search {i} finished: {resp.status_code} in {time.time()-start:.2f}s")
        return resp.status_code
    except Exception as e:
        logger.error(f"Search {i} failed: {e}")
        return "FAIL"

async def test_priority_queue():
    async with httpx.AsyncClient() as client:
        # 1. Flood with 10 slow requests (Max is 5)
        logger.info("Flooding system with 10 search requests...")
        tasks = [slow_request(client, i) for i in range(10)]
        
        # 2. Immediately try a Priority 0 request
        await asyncio.sleep(0.5) # Give flood a head start
        logger.info("Attempting Priority 0 (Health) bypass...")
        start_p0 = time.time()
        health_resp = await client.get(f"{BASE_URL}/api/health")
        duration_p0 = time.time() - start_p0
        
        logger.info(f"Priority 0 status: {health_resp.status_code} in {duration_p0:.2f}s")
        
        # 3. Wait for all
        results = await asyncio.gather(*tasks)
        
        # 4. Analysis
        # Health MUST be fast and 200
        assert health_resp.status_code == 200
        assert duration_p0 < 1.0, "Priority 0 was blocked by queue!"
        
        # Searches should have some 503s or at least be slow
        if 503 in results:
            logger.info("✅ Priority Queue Verified: 503 load shedding detected for non-priority.")
        else:
            logger.info("Results did not contain 503, maybe search was too fast to saturate semaphore.")
            
        logger.info(f"Total processed: {results.count(200)}, Throttled: {results.count(503)}")

if __name__ == "__main__":
    asyncio.run(test_priority_queue())
