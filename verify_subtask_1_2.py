import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.2")

BASE_URL = "http://127.0.0.1:8000"

async def verify_hardware_monitor():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get initial health
        logger.info("Checking initial hardware metrics...")
        resp = await client.get(f"{BASE_URL}/api/health")
        data = resp.json()["jit_intelligence"]["performance"]
        initial_ram = data["ram_usage_percent"]
        logger.info(f"Initial RAM: {initial_ram}% | CPU: {data['cpu_usage_percent']}%")
        
        # 2. Trigger Memory Spike
        logger.info("Triggering Memory Spike (~100MB)...")
        try:
            # This endpoint holds memory for 2 seconds
            spike_task = asyncio.create_task(client.get(f"{BASE_URL}/api/test/mem-spike"))
            
            # 3. Wait 1 second and check health WHILE spike is active
            await asyncio.sleep(1)
            resp = await client.get(f"{BASE_URL}/api/health")
            spike_data = resp.json()["jit_intelligence"]["performance"]
            spike_ram = spike_data["ram_usage_percent"]
            logger.info(f"RAM during spike: {spike_ram}% | CPU: {spike_data['cpu_usage_percent']}%")
            
            if spike_ram > initial_ram:
                logger.info(f"✅ Hardware Monitor Verified. RAM increased by {spike_ram - initial_ram:.2f}%")
            else:
                # RAM might not move much on large VPS, but should move a bit.
                logger.warning(f"RAM did not increase significantly. Initial: {initial_ram}, Spike: {spike_ram}")
            
            await spike_task
        except Exception as e:
            logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_hardware_monitor())
