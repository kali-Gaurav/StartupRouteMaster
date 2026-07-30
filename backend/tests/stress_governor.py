import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stress.governor")

async def hammer_search(client: httpx.AsyncClient, worker_id: int):
    """Simulates a heavy search request."""
    url = "http://127.0.0.1:8000/api/v3/search/unified"
    params = {"source": "SRE", "destination": "LKO", "date": "2026-10-10"}
    
    start = time.time()
    try:
        resp = await client.get(url, params=params, timeout=30)
        duration = time.time() - start
        status = resp.status_code
        logger.info(f"[Worker {worker_id}] Status: {status} | Time: {duration:.2f}s")
        return status
    except Exception as e:
        logger.error(f"[Worker {worker_id}] Failed: {e}")
        return 500

async def monitor_governor(client: httpx.AsyncClient):
    """Polls governor stats during the stress test."""
    url = "http://127.0.0.1:8000/api/v3/governor/stats"
    for _ in range(10):
        try:
            resp = await client.get(url)
            stats = resp.json()
            logger.info(f"📊 [TELEMETRY] CPU: {stats['vps']['cpu_p']}% | RAM: {stats['vps']['ram_p']}% | Throttle: {stats['governor']['throttle_factor']}")
        except: pass
        await asyncio.sleep(2)

async def run_stress_test():
    """Launches 20 concurrent requests to trigger throttling."""
    logger.info("🚀 Starting Phase 9 Stress Test: Governor Stability Benchmark...")
    
    async with httpx.AsyncClient(timeout=40) as client:
        # Start monitor
        monitor_task = asyncio.create_task(monitor_governor(client))
        
        # Launch workers
        tasks = [hammer_search(client, i) for i in range(15)]
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        throttled = results.count(503)
        success = results.count(200)
        logger.info(f"🏁 Stress Test Complete. Success: {success} | Throttled (503): {throttled}")
        
        if throttled > 0:
            logger.info("✅ SUCCESS: Governor successfully shed load during peak pressure.")
        else:
            logger.warning("⚠️ NOTICE: Governor did not trigger. System might have been too fast or limits too high for local dev.")

        await monitor_task

if __name__ == "__main__":
    asyncio.run(run_stress_test())
