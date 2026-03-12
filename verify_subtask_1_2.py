import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.2")

BASE_URL = "http://127.0.0.1:8000"

async def test_observability():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Success case
        logger.info("Triggering 200 OK...")
        resp = await client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        
        # 2. 404 case
        logger.info("Triggering 404 Not Found...")
        resp = await client.get(f"{BASE_URL}/api/no-path")
        assert resp.status_code == 404
        
        # 3. 500 case (Deliberate fail if possible)
        # We'll try a search with bad data that might trigger a 500 in my new hardened middleware
        logger.info("Triggering potential 500...")
        payload = {"source": "INVALID", "destination": "INVALID", "date": "2026-03-15"}
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search (invalid) status: {resp.status_code}")

async def main():
    await test_observability()
    logger.info("Requests sent. Please check backend logs for 'HTTP GET /api/health -> 200' etc.")

if __name__ == "__main__":
    asyncio.run(main())
