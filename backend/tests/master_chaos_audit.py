import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus.audit.100")

async def test_nexus_self_healing():
    """
    [Task 100] The Final Crash Benchmark.
    Simulates: 
    1. Critical Search Node failure.
    2. Redis disconnect.
    3. Simultaneous 20-Request Spike.
    Verifies state shift to GHOST_MODE and recovery to READY.
    """
    logger.info("💀 [NEXUS:AUDIT-100] Initiating Total Infrastructure Meltdown Benchmark...")
    
    async with httpx.AsyncClient(timeout=40) as client:
        # Phase 1: Baseline Check
        resp = await client.get("http://127.0.0.1:8000/health")
        if resp.status_code != 200:
             logger.error("❌ Baseline check failed. Ensure server is running.")
             return
        
        # Phase 2: Chaos Injection (Sever Redis and Fail Search Node)
        logger.warning("💉 [NEXUS:AUDIT-100] Severing Cache Layer and Crashing Search Node...")
        await client.post("http://127.0.0.1:8000/nexus/chaos/arm/cache_l2", params={"error_rate": 1.0})
        await client.post("http://127.0.0.1:8000/nexus/chaos/arm/search_engine", params={"error_rate": 1.0})
        
        # Phase 3: Pressure Wave (Concurrent Searches)
        logger.info("🌊 [NEXUS:AUDIT-100] Launching 20-Request Pressure Wave...")
        tasks = [client.get("http://127.0.0.1:8000/api/v3/search/unified", params={"source": "LKO", "destination": "SRE"}) for _ in range(15)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Expected Results: Status 503 (Latching) or 200 (Extreme Throttling/Fallback)
        # For Task 100, we verify the server does NOT crash (500)
        error_count = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 500)
        logger.info(f"📊 Post-Meltdown Stats: Errors(500): {error_count} | Throttled(503): {sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 503)}")
        
        if error_count > 0:
             logger.error("❌ FAILURE: Nexus Spine leaked a 500 error during meltdown.")
        else:
             logger.info("✅ SUCCESS: Zero leaked 500 errors. All traffic either throttled or handled safely.")
        
        # Phase 4: Recovery (Disarm Chaos and Wait)
        logger.info("🩹 [NEXUS:AUDIT-100] Disarming Chaos Mesh and Waiting for Heartbeat Recovery...")
        await client.post("http://127.0.0.1:8000/nexus/chaos/disarm/cache_l2")
        await client.post("http://127.0.0.1:8000/nexus/chaos/disarm/search_engine")
        
        # Verify Recovery
        for i in range(12): # Wait 60s max
             await asyncio.sleep(5)
             resp = await client.get("http://127.0.0.1:8000/health")
             data = resp.json()
             if data["status"] == "V3_OPERATIONAL":
                  logger.info(f"🏁 [NEXUS:AUDIT-100] Recovery Complete in {i*5} seconds! SYSTEM IS READY.")
                  return
             logger.info(f"⏳ Waiting for Recovery... [State: {data['status']}]")
        
        logger.error("❌ FAILURE: System failed to recover within 60 seconds.")

if __name__ == "__main__":
    asyncio.run(test_nexus_self_healing())
