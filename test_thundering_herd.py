import asyncio
import httpx
import time
import statistics
from datetime import datetime

BASE_URL = "http://localhost:8000"
CONCURRENT_REQUESTS = 1000 # Scaling down from 10k to 1k for local stability, but logic is same

async def fire_request(client, req_id):
    try:
        # We hit /api/stats which triggers the GRAPH node in our new JIT DAG
        start = time.time()
        resp = await client.get(f"{BASE_URL}/api/stats", timeout=60)
        duration = time.time() - start
        return {
            "id": req_id,
            "status": resp.status_code,
            "duration": duration,
            "init_complete": resp.json().get("initialized", False)
        }
    except Exception as e:
        return {"id": req_id, "error": str(e)}

async def run_thundering_herd_test():
    print(f"🚀 Starting Thundering Herd Test: {CONCURRENT_REQUESTS} concurrent requests...")
    print(f"Target: {BASE_URL}/api/stats (Triggers JIT GRAPH loading)")
    
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        
        # Fire all requests simultaneously
        tasks = [fire_request(client, i) for i in range(CONCURRENT_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
        total_duration = time.time() - start_time

    # Analyze results
    successes = [r for r in results if r.get("status") == 200]
    errors = [r for r in results if "error" in r]
    durations = [r["duration"] for r in successes]

    print("\n--- Test Results ---")
    print(f"Total Requests: {CONCURRENT_REQUESTS}")
    print(f"Successes: {len(successes)}")
    print(f"Errors: {len(errors)}")
    print(f"Total Test Wall Time: {total_duration:.2f}s")
    
    if durations:
        print(f"Avg Latency: {statistics.mean(durations):.2f}s")
        print(f"Max Latency: {max(durations):.2f}s")
        print(f"Min Latency: {min(durations):.2f}s")
        
    # Crucial Verification: If Thundering Herd protection works, 
    # the server logs should only show ONE initialization message, 
    # and all requests should eventually get 'initialized: True'
    all_init = all(r.get("init_complete") for r in successes)
    print(f"All requests reported 'initialized: True': {all_init}")
    
    if errors:
        print(f"First Error: {errors[0]['error']}")

if __name__ == "__main__":
    # Give the server a moment if just started
    time.sleep(2)
    asyncio.run(run_thundering_herd_test())
