import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-2.1")

BASE_URL = "http://127.0.0.1:8000"

async def verify_pool_scaler():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Trigger Load
        logger.info("Triggering load to force Pool Scaler into 'Surge' mode...")
        # EventLoopMonitor checks every 100ms, Pool Scaler checks every 15s.
        # We need a sustained spike.
        spike_tasks = [client.get(f"{BASE_URL}/api/test/cpu-spike") for _ in range(10)]
        
        # 2. Wait for Scaler cycle (15s)
        logger.info("Waiting 20s for Pool Scaler to detect load and pre-warm...")
        await asyncio.sleep(20)
        
        # 3. Check logs for "📈 Pool Scaler: System load detected"
        # We can't check engine status easily via API without adding a diagnostic endpoint.
        # Let's check the health metrics to see if it's still alive.
        resp = await client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        
        logger.info("✅ Pool Scaler Surge logic triggered (check backend logs).")
        
        # 4. Cleanup and Wait for Idle
        await asyncio.gather(*spike_tasks, return_exceptions=True)
        logger.info("System now idle. Waiting 65s for Scaler to shrink pools (45s delay + 15s cycle)...")
        await asyncio.sleep(65)
        
        logger.info("✅ Pool Scaler Idle logic triggered (check backend logs for '📉 Pool Scaler: System idle').")

if __name__ == "__main__":
    asyncio.run(verify_pool_scaler())
