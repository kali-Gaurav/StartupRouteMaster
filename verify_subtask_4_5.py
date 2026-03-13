import asyncio
import httpx
import logging
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.metrics import SurgeLevel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.5")

BASE_URL = "http://127.0.0.1:8000"

async def test_surge_l3_auth_bypass():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Mock Critical Surge in the API Search module specifically
        logger.info("Setting Surge Level to CRITICAL...")
        mock_metrics = MagicMock()
        mock_metrics.surge_level = SurgeLevel.CRITICAL
        
        # WE MUST PATCH WHERE IT IS USED
        with patch('backend.api.search.jit_metrics', mock_metrics):
            # A. Test Unauthenticated Request (Should fail 503)
            logger.info("A. Testing unauthenticated request (Should be 503)...")
            payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15", "budget": "all"}
            resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
            logger.info(f"Status: {resp.status_code}")
            
            # If we get 500, it might be because patching failed or search service crashed early
            if resp.status_code == 500:
                logger.error(f"Server returned 500: {resp.text}")
            
            assert resp.status_code == 503
            assert "peak capacity" in resp.json()["message"].lower()
            logger.info("✅ Unauthenticated request correctly blocked.")

if __name__ == "__main__":
    asyncio.run(test_surge_l3_auth_bypass())
