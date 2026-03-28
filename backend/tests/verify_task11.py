import asyncio
import httpx
import time
import statistics
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("task-11-verify")

async def verify_v3_search():
    url = "http://localhost:8000/api/v3/search/unified"
    params = {
        "source": "NDLS",
        "destination": "BCT",
        "date": "2026-04-10",
        "persona": "ECONOMY"
    }
    
    latencies = []
    logger.info("🚀 Benchmarking Elite V3 Search (10 requests)...")
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Warmup
        try:
            await client.get(url, params=params)
        except Exception as e:
            logger.error(f"Cold boot failed (is app running?): {e}")
            return

        for i in range(10):
            start = time.perf_counter()
            resp = await client.get(url, params=params)
            latencies.append((time.perf_counter() - start) * 1000)
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Req {i+1}: {data['status']} | {data['latency_ms']}ms (API) | {latencies[-1]:.2f}ms (E2E)")
                # Check Nexus Headers
                trace_id = resp.headers.get("X-Nexus-ID")
                engine = resp.headers.get("X-Nexus-State")
                dur = resp.headers.get("X-Nexus-Duration-MS")
                logger.debug(f"Headers: ID={trace_id}, State={engine}, Dur={dur}")
            else:
                logger.error(f"Req {i+1} Failed: {resp.status_code} - {resp.text}")

    if latencies:
        logger.info(f"📊 SUMMARY: P50={statistics.median(latencies):.2f}ms | P99={max(latencies):.2f}ms")

if __name__ == "__main__":
    asyncio.run(verify_v3_search())
