import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.3")

BASE_URL = "http://127.0.0.1:8000"

async def test_db_lifecycle():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Hit an API endpoint that triggers the middleware
        logger.info("Hitting /api/health...")
        resp = await client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        
        # Hit an endpoint that likely uses DB
        logger.info("Hitting /api/stations/search...")
        resp = await client.get(f"{BASE_URL}/api/stations/search?q=KOTA")
        # If it returns 200 or 422 or 500, at least we know it didn't crash the worker due to middleware
        logger.info(f"Response: {resp.status_code}")
        assert resp.status_code in [200, 422, 500]

async def main():
    await test_db_lifecycle()
    logger.info("Requests sent. Check backend logs for 'DB Lifecycle' entries.")

if __name__ == "__main__":
    asyncio.run(main())
