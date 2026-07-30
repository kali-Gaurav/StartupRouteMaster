import asyncio
import httpx
import logging
import time
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("workflow_sim")

BACKEND_URL = "http://localhost:8000"

async def simulate_workflow():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Ping Check
        logger.info("📡 Step 1: Checking Backend Connectivity...")
        try:
            resp = await client.get(f"{BACKEND_URL}/ping")
            logger.info(f"✅ Ping Response: {resp.json()}")
        except Exception as e:
            logger.error(f"❌ Backend not reachable: {e}")
            return

        # 2. Health & Nexus Readiness
        logger.info("📡 Step 2: Verifying Nexus Readiness...")
        resp = await client.get(f"{BACKEND_URL}/health")
        health = resp.json()
        logger.info(f"✅ Health Status: {health.get('status')} | Nexus: {health.get('components', {}).get('nexus')}")

        # 3. User Search Request (JAT -> CAPE)
        logger.info("📡 Step 3: Simulating User Search (JAT -> CAPE)...")
        
        # In V3, unified search is a GET request to /api/v3/search/unified
        search_params = {
            "source": "JAT",
            "destination": "CAPE",
            "date": "2026-04-28",
            "persona": "COMFORT",
            "tier": "ELITE"
        }
        
        start_time = time.time()
        search_url = f"{BACKEND_URL}/api/v3/search/unified"
        
        try:
            resp = await client.get(search_url, params=search_params)
            latency = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                # V3 response structure: data: { journeys: [...] }
                journeys = data.get("data", {}).get("journeys", [])
                logger.info(f"✅ Workflow Success! Yield: {len(journeys)} routes | Latency: {latency:.2f}ms")
                
                # Check for multi-transfer
                for i, r in enumerate(journeys[:3]):
                    segs = r.get("segments", [])
                    logger.info(f"   Route #{i+1}: {len(segs)} legs | Engine: {r.get('metadata', {}).get('engine')}")
            else:
                logger.error(f"❌ Search Failed with status {resp.status_code}: {resp.text}")
                
        except Exception as e:
            logger.error(f"❌ Error during search simulation: {e}")

if __name__ == "__main__":
    asyncio.run(simulate_workflow())
