import asyncio
import logging
import time
import random
from services.safety_dispatch_manager import SafetyDispatchManager
from core.infrastructure.redis_manager import async_redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos.audit")

async def run_chaos_audit(concurrency: int = 50):
    """
    [RM-Q-010] Chaos Signal Stress Test.
    Simulates high-concurrency SOS triggers and measures system performance.
    """
    logger.info(f"🔥 Starting Chaos Audit with {concurrency} concurrent SOS alerts...")
    start_time = time.time()
    
    # 1. Setup mock station/sathi data if needed (Assumed active in Redis)
    
    # 2. Trigger concurrent incidents
    tasks = []
    for i in range(concurrency):
        lat = 28.6139 + (random.random() * 0.1) # Around New Delhi
        lon = 77.2090 + (random.random() * 0.1)
        tasks.append(SafetyDispatchManager.create_incident(
            user_id=f"user_{i}",
            lat=lat,
            lon=lon,
            incident_type="CHAOS_TEST"
        ))

    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    duration = end_time - start_time
    avg_latency = (duration / concurrency) * 1000

    logger.info(f"✅ Audit Complete.")
    logger.info(f"⏱ Total Time: {duration:.2f}s")
    logger.info(f"⚡ Avg Latency per Incident: {avg_latency:.2f}ms")
    
    # 3. Validation Logic
    active_incidents = await async_redis_client.smembers(SafetyDispatchManager.ACTIVE_INCIDENTS_SET)
    logger.info(f"📊 Active Incidents in State Machine: {len(active_incidents)}")
    
    if len(active_incidents) == concurrency:
        logger.info("✨ SYSTEM INTEGRITY VERIFIED: All incidents tracked correctly.")
    else:
        logger.error("❌ SYSTEM FAILURE: State machine mismatch!")

if __name__ == "__main__":
    asyncio.run(run_chaos_audit())
