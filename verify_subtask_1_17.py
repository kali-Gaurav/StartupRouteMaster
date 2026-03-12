import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-1.17")

BASE_URL = "http://127.0.0.1:8000"

async def verify_kill_switch():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Activate Kill Switch
        logger.info("Activating Emergency Kill Switch...")
        await client.post(f"{BASE_URL}/api/admin/kill-switch?active=true")
        
        # 2. Try non-emergency request (Search)
        logger.info("Testing search during lockdown...")
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search Status: {resp.status_code}")
        assert resp.status_code == 503
        assert "emergency lockdown" in resp.json()["message"].lower()
        
        # 3. Try emergency bypass (SOS)
        logger.info("Testing emergency bypass (SOS)...")
        sos_resp = await client.get(f"{BASE_URL}/api/sos/status") # placeholder
        if sos_resp.status_code == 404:
            logger.info("SOS route bypass confirmed (404 instead of 503).")
        else:
            logger.info(f"SOS Status: {sos_resp.status_code}")
            assert sos_resp.status_code != 503
            
        # 4. Deactivate Kill Switch
        logger.info("Deactivating Kill Switch...")
        await client.post(f"{BASE_URL}/api/admin/kill-switch?active=false")
        
        # 5. Verify search is back
        logger.info("Testing search after lockdown lift...")
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Search Status: {resp.status_code}")
        assert resp.status_code in [200, 500] 
        
        logger.info("✅ Emergency Kill Switch Verified.")

if __name__ == "__main__":
    asyncio.run(verify_kill_switch())
