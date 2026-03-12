import asyncio
import httpx
import random
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("extreme-fuzzer")

BASE_URL = "http://127.0.0.1:8000"

async def chaotic_client(worker_id):
    """Simulates a user that may drop connection or spam requests."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for i in range(50):
            try:
                # Randomly pick an endpoint
                endpoint = random.choice([
                    "/api/health", 
                    "/api/search/", 
                    "/api/v2/search/unified?source=KOTA&destination=NDLS&date=2026-03-15",
                    "/non-existent"
                ])
                
                # Randomly decide to drop connection early
                if random.random() < 0.3:
                    async with client.stream("GET" if "search" not in endpoint else "POST", f"{BASE_URL}{endpoint}") as response:
                        await asyncio.sleep(random.uniform(0, 0.05))
                        await response.aclose()
                else:
                    if "POST" in endpoint or "/api/search/" in endpoint:
                        await client.post(f"{BASE_URL}/api/search/", json={"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"})
                    else:
                        await client.get(f"{BASE_URL}{endpoint}")
            except Exception:
                pass
            
            if i % 10 == 0:
                await asyncio.sleep(random.uniform(0.1, 0.3))

async def run_extreme_fuzz(worker_count=100):
    logger.info(f"🔥 Starting Extreme Fuzzing with {worker_count} concurrent workers...")
    start = time.time()
    
    workers = [chaotic_client(i) for i in range(worker_count)]
    await asyncio.gather(*workers)
    
    duration = time.time() - start
    logger.info(f"🏁 Fuzzing complete in {duration:.2f}s.")
    
    # Final health check to see if server is alive
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/health")
        if resp.status_code == 200:
            logger.info("✅ Server SURVIVED extreme fuzzing. Protocol stability confirmed.")
            logger.info(f"Final Metrics: {resp.json()['jit_intelligence']['performance']}")
        else:
            logger.error(f"❌ Server is UNHEALTHY after fuzzing: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(run_extreme_fuzz())
