import asyncio
import httpx
import logging
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.7")

BASE_URL = "http://127.0.0.1:8000"

async def test_penalty_box_via_ratelimit():
    async with httpx.AsyncClient(timeout=10.0) as client:
        logger.info("Spamming requests to trigger Rate Limit -> Penalty Box...")
        
        jailed = False
        # Threshold is 10
        for i in range(150):
            try:
                # Use /api/search/ which is rate limited and non-blocking
                resp = await client.post(f"{BASE_URL}/api/search/", json={"source":"A", "destination":"B"})
                if resp.status_code == 403:
                    logger.info(f"🚀 SUCCESS: IP JAILED at request {i+1}!")
                    jailed = True
                    break
                if resp.status_code == 429:
                    if i % 10 == 0:
                        logger.info(f"Rate limited (429)... (Count: {i+1})")
            except Exception as e:
                logger.error(f"Request failed: {e}")
        
        assert jailed, "IP was never jailed after spams."
        
        # Verify block persists on health check
        resp = await client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 403
        logger.info("✅ Persistence verified: Health check also blocked.")

        logger.info("✅ Subtask 4.7: Penalty Box Verified.")

if __name__ == "__main__":
    asyncio.run(test_penalty_box_via_ratelimit())
