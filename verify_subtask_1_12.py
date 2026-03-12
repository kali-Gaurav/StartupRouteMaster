import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.12")

BASE_URL = "http://127.0.0.1:8000"

async def verify_maintenance():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Enable Maintenance Mode
        logger.info("Enabling Maintenance Mode...")
        await client.post(f"{BASE_URL}/api/admin/maintenance?enabled=true")
        
        # 2. Try regular request (Search)
        logger.info("Testing search during maintenance...")
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search Status: {resp.status_code}")
        assert resp.status_code == 503
        assert "maintenance" in resp.json()["message"].lower()
        
        # 3. Try bypass request (Health)
        logger.info("Testing health bypass...")
        health_resp = await client.get(f"{BASE_URL}/api/health")
        logger.info(f"Health Status: {health_resp.status_code}")
        assert health_resp.status_code == 200
        
        # 4. Disable Maintenance Mode
        logger.info("Disabling Maintenance Mode...")
        await client.post(f"{BASE_URL}/api/admin/maintenance?enabled=false")
        
        # 5. Verify search is back
        logger.info("Testing search after maintenance...")
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search Status: {resp.status_code}")
        assert resp.status_code in [200, 500] # 500 is okay as long as not 503 maintenance
        
        logger.info("✅ Maintenance Mode Verified.")

if __name__ == "__main__":
    asyncio.run(verify_maintenance())
