import asyncio
import httpx
import time
import statistics
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos-test")

BASE_URL = "http://localhost:8000"

async def trigger_sos(client, i):
    payload = {
        "lat": 28.6139 + (i * 0.001), 
        "lng": 77.2090,
        "name": f"Chaos User {i}",
        "phone": f"+91-{i:010d}",
        "extra": "CHAOS TEST BURST"
    }
    start = time.perf_counter()
    try:
        resp = await client.post(f"{BASE_URL}/api/sos/", json=payload, timeout=10.0)
        latency = time.perf_counter() - start
        return resp.status_code, latency
    except Exception as e:
        return 500, time.perf_counter() - start

async def check_system_health(client):
    start = time.perf_counter()
    try:
        resp = await client.get(f"{BASE_URL}/health", timeout=5.0)
        return resp.status_code, time.perf_counter() - start
    except:
        return 500, 5.0

async def run_chaos_test():
    print("--- 🌪️ Task 44: Chaos Engineering & Stress Test ---")
    print("Goal: Verify SOS burst doesn't starve the API and recovery is instant.")
    
    async with httpx.AsyncClient() as client:
        # 1. Warm-up Health Check
        status, lat = await check_system_health(client)
        print(f"Baseline Health Latency: {lat:.4f}s (Status: {status})")
        
        # 2. Burst 200 SOS Requests
        print(f"\n[Step 1] Triggering 200 concurrent SOS alerts...")
        start_time = time.perf_counter()
        tasks = [trigger_sos(client, i) for i in range(200)]
        
        # Monitor health *during* the burst
        health_during_burst = asyncio.create_task(check_system_health(client))
        
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time
        
        # 3. Analyze Results
        codes = [r[0] for r in results]
        latencies = [r[1] for r in results]
        
        success_rate = (codes.count(200) / 200) * 100
        avg_lat = statistics.mean(latencies)
        p95_lat = statistics.quantiles(latencies, n=20)[18] # 95th percentile
        
        h_status, h_lat = await health_during_burst
        
        print(f"\n--- Burst Results ---")
        print(f"Success Rate: {success_rate}%")
        print(f"Avg Latency: {avg_lat:.4f}s")
        print(f"P95 Latency: {p95_lat:.4f}s")
        print(f"Total Burst Duration: {total_time:.2f}s")
        print(f"Health Latency DURING Burst: {h_lat:.4f}s (Status: {h_status})")
        
        # 4. Recovery Test
        print("\n[Step 2] Testing Recovery Speed (Immediate)...")
        rec_status, rec_lat = await check_system_health(client)
        print(f"Post-Burst Health Latency: {rec_lat:.4f}s (Status: {rec_status})")
        
        # 5. Gap Check: Redis Stability
        print("\n[Step 3] Verifying Redis Integrity...")
        all_sos_resp = await client.get(f"{BASE_URL}/api/sos/all")
        count = len(all_sos_resp.json())
        print(f"Total SOS Events in storage: {count}")
        
        if success_rate > 95 and h_lat < 1.0 and rec_lat < 0.1:
            print("\n🏆 CHAOS TEST PASSED: System is resilient to safety traffic storms.")
        else:
            print("\n❌ CHAOS TEST FAILED: System showed significant degradation.")

if __name__ == "__main__":
    asyncio.run(run_chaos_test())
