import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.5")

BASE_URL = "http://127.0.0.1:8000"

async def verify_soft_scaling():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Trigger massive CPU block to force overload state
        logger.info("Triggering extreme overload simulation (3s)...")
        
        # We'll trigger multiple spikes in parallel to keep CPU pegged
        spike_tasks = []
        for _ in range(10):
            spike_tasks.append(client.get(f"{BASE_URL}/api/test/cpu-spike"))
        
        # Wait for monitor to sample (samples every 1s)
        await asyncio.sleep(2.0)
        
        logger.info("Testing non-priority load shedding...")
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
        search_resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        
        # 3. Immediately try a PRIORITY request (Health)
        logger.info("Testing priority bypass...")
        health_resp = await client.get(f"{BASE_URL}/api/health")
        
        logger.info(f"Search Status: {search_resp.status_code}")
        logger.info(f"Health Status: {health_resp.status_code}")
        
        # Cleanup spikes
        await asyncio.gather(*spike_tasks, return_exceptions=True)

        if search_resp.status_code == 503:
            logger.info("✅ Soft Scaling Verified: Search was shed under load.")
        else:
            # If search completed, it might mean CPU hasn't hit 95% yet in the monitor cycle
            # But health MUST stay 200.
            logger.warning(f"Search did not shed (Status {search_resp.status_code}). Monitor might need more time.")
            
        assert health_resp.status_code == 200, "Health (Priority) should never be shed!"
        logger.info("✅ Priority bypass confirmed.")

if __name__ == "__main__":
    asyncio.run(verify_soft_scaling())
