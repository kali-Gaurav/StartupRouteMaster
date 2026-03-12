import asyncio
import httpx
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.13")

BASE_URL = "http://127.0.0.1:8000"

async def hammer_and_drop(client, i):
    """Sends a request and randomly drops it or waits."""
    url = f"{BASE_URL}/api/health"
    try:
        if random.random() > 0.5:
            # Full request
            resp = await client.get(url)
            return resp.status_code
        else:
            # Aborted request
            async with client.stream("GET", url) as response:
                await asyncio.sleep(random.uniform(0, 0.01))
                await response.aclose()
                return "ABORTED"
    except Exception:
        return "ERROR"

async def test_h11_stability(count=100):
    logger.info(f"Firing {count} chaotic requests to test ASGI/h11 stability...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        tasks = [hammer_and_drop(client, i) for i in range(count)]
        results = await asyncio.gather(*tasks)
        
        stats = {
            "200": results.count(200),
            "ABORTED": results.count("ABORTED"),
            "ERROR": results.count("ERROR")
        }
        logger.info(f"Chaotic Results: {stats}")
        # If the server is still alive and responding to new requests, we pass.
        resp = await client.get(f"{BASE_URL}/api/health")
        if resp.status_code == 200:
            logger.info("✅ Server survived the chaos. h11 state transitions are stable.")
        else:
            logger.error(f"❌ Server is unhealthy after load: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_h11_stability())
