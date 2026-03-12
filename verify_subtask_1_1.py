import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.1")

BASE_URL = "http://127.0.0.1:8000"

async def verify_monitor():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get initial health
        logger.info("Checking initial event loop latency...")
        resp = await client.get(f"{BASE_URL}/api/health")
        data = resp.json()
        logger.info(f"Health Data: {data}")
        
        # Check jit_intelligence nesting
        if "performance" in data:
            perf = data["performance"]
        elif "jit_intelligence" in data and "performance" in data["jit_intelligence"]:
            perf = data["jit_intelligence"]["performance"]
        else:
            logger.error(f"Performance key missing! Keys: {data.keys()}")
            return

        initial_latency = perf["event_loop_latency_ms"]
        logger.info(f"Initial Latency: {initial_latency}ms")
        
        # 2. Trigger CPU Spike
        logger.info("Triggering CPU Spike (500ms block)...")
        # We don't await this because it blocks the server, 
        # but we want to see the monitor pick it up in next health check.
        try:
            await client.get(f"{BASE_URL}/api/test/cpu-spike")
        except httpx.ReadTimeout:
            logger.warning("Spike request timed out as expected (it blocks the loop).")

        # 3. Wait for monitor to update
        logger.info("Waiting for monitor to catch up...")
        await asyncio.sleep(2)
        
        # 4. Check health again
        resp = await client.get(f"{BASE_URL}/api/health")
        data = resp.json()
        if "performance" in data:
            perf = data["performance"]
        elif "jit_intelligence" in data and "performance" in data["jit_intelligence"]:
            perf = data["jit_intelligence"]["performance"]
        else:
            logger.error("Performance key missing in second check!")
            return

        new_latency = perf["event_loop_latency_ms"]
        logger.info(f"Post-Spike Latency: {new_latency}ms")
        
        if new_latency > initial_latency:
            logger.info(f"✅ Event Loop Monitor Verified. Detectable increase: {new_latency - initial_latency:.2f}ms")
        else:
            logger.error("❌ Monitor failed to detect significant latency increase.")

if __name__ == "__main__":
    asyncio.run(verify_monitor())
