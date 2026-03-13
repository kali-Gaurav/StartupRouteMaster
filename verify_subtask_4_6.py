import asyncio
import httpx
import logging
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.6")

BASE_URL = "http://127.0.0.1:8000"

async def test_adaptive_retry_header():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Enable Maintenance Mode to trigger a 503
        logger.info("Enabling Maintenance Mode to trigger 503...")
        await client.post(f"{BASE_URL}/api/admin/maintenance?enabled=true")
        
        try:
            # 2. Case: NORMAL Surge (Should be 5s)
            logger.info("A. Testing NORMAL surge retry-after...")
            await client.get(f"{BASE_URL}/api/health?surge_override=NORMAL")
            resp = await client.post(f"{BASE_URL}/api/search/", json={"source":"A", "destination":"B", "date":"2026-01-01"})
            
            retry_val = resp.headers.get("Retry-After")
            logger.info(f"Status: {resp.status_code}, Retry-After: {retry_val}")
            assert resp.status_code == 503
            assert int(retry_val) >= 5 # Confirm it is at least the base

            # 3. Case: HIGH Surge (Should be 30s)
            logger.info("B. Testing HIGH surge retry-after...")
            await client.get(f"{BASE_URL}/api/health?surge_override=HIGH")
            resp = await client.post(f"{BASE_URL}/api/search/", json={"source":"A", "destination":"B", "date":"2026-01-01"})
            
            retry_val = resp.headers.get("Retry-After")
            logger.info(f"Status: {resp.status_code}, Retry-After: {retry_val}")
            assert retry_val == "30"

            # 4. Case: CRITICAL Surge (Should be 60s)
            logger.info("C. Testing CRITICAL surge retry-after...")
            await client.get(f"{BASE_URL}/api/health?surge_override=CRITICAL")
            resp = await client.post(f"{BASE_URL}/api/search/", json={"source":"A", "destination":"B", "date":"2026-01-01"})
            
            retry_val = resp.headers.get("Retry-After")
            logger.info(f"Status: {resp.status_code}, Retry-After: {retry_val}")
            assert retry_val == "60"

            logger.info("✅ Subtask 4.6: Dynamic Retry-After Verified.")

        finally:
            # Cleanup
            await client.post(f"{BASE_URL}/api/admin/maintenance?enabled=false")
            await client.get(f"{BASE_URL}/api/health?surge_override=NORMAL")

if __name__ == "__main__":
    asyncio.run(test_adaptive_retry_header())
