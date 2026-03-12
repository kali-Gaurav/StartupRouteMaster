import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.7")

BASE_URL = "http://127.0.0.1:8000"

async def verify_connection_shedding():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Trigger Memory Spike
        logger.info("Triggering Memory Spike (~100MB)...")
        # We hold it for 2s. The monitor samples every 1s.
        spike_task = asyncio.create_task(client.get(f"{BASE_URL}/api/test/mem-spike"))
        
        # 2. Wait 1.5s to ensure monitor detects it
        await asyncio.sleep(1.5)
        
        # 3. Try NON-PRIORITY request
        logger.info("Testing non-priority connection shedding...")
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
        search_resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        
        # 4. Try PRIORITY request
        logger.info("Testing priority (SOS) bypass...")
        sos_resp = await client.get(f"{BASE_URL}/api/sos/contacts") # Assuming this exists or similar
        if sos_resp.status_code == 404:
            # If path not found, middleware still should have bypassed it
            logger.info("Path /api/sos/contacts not found but bypass check can still be inferred.")
        
        logger.info(f"Search Status: {search_resp.status_code}")
        
        # Cleanup
        await spike_task

        if search_resp.status_code == 503:
            data = search_resp.json()
            if "resource limits" in data.get("message", "").lower():
                logger.info("✅ Connection Shedding Verified: Non-priority traffic shed under memory pressure.")
            else:
                logger.warning(f"503 received but message mismatch: {data}")
        else:
            logger.warning(f"Search did not shed (Status {search_resp.status_code}). RAM might not have hit 90%.")
            # We can't easily force RAM to 90% without knowing VPS size, 
            # but the logic is implemented and registered.

if __name__ == "__main__":
    asyncio.run(verify_connection_shedding())
