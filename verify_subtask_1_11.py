import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.11")

BASE_URL = "http://127.0.0.1:8000"

async def test_circuit_breaker():
    logger.info("Testing Routing Circuit Breaker...")
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger failures (Using invalid search data to get 422/500)
        # Note: Breaker triggers on >= 500. Let's see if we can force a 500.
        # We'll use a known route that we can 'crash' if needed, or just simulate hits.
        
        logger.info("Step 1: Pushing 5 requests that trigger 500 via invalid budget category...")
        for i in range(5):
            # 'BOOM' budget should crash Persona(budget_category) inside SearchService
            payload = {
                "source": "KOTA", 
                "destination": "NDLS", 
                "date": "2026-03-15",
                "budget": "BOOM"
            }
            resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
            # logger.info(f"Req {i+1} status: {resp.status_code}")
            
        # 2. Check if next request is blocked with 503
        logger.info("Step 2: Checking if breaker is OPEN...")
        payload = {"source": "KOTA", "destination": "NDLS", "date": "2026-03-15"}
        resp = await client.post(f"{BASE_URL}/api/search/", json=payload)
        logger.info(f"Final Request Status: {resp.status_code}")
        
        if resp.status_code == 503:
            data = resp.json()
            if "overloaded" in data.get("message", "").lower():
                logger.info("✅ Circuit Breaker Verified: Search is throttled.")
            else:
                logger.info(f"Status 503 received but message mismatch: {data}")
        else:
            logger.warning(f"❌ Breaker did not trip. Status: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())
