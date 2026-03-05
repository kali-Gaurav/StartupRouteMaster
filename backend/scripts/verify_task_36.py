import httpx
import asyncio
import time

async def verify():
    print("--- 🗺️ Task 36: Real-time Incident Visualizer Verification ---")
    
    url_base = "http://127.0.0.1:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger two incidents in the same grid
        # New Delhi Grid (Approx 28.6, 77.2)
        print("\n[Step 1] Triggering 2 incidents in New Delhi cluster...")
        p1 = {"lat": 28.6139, "lng": 77.2090, "name": "Cluster User 1"}
        p2 = {"lat": 28.6145, "lng": 77.2095, "name": "Cluster User 2"}
        
        await client.post(f"{url_base}/", json=p1)
        await client.post(f"{url_base}/", json=p2)
        
        # 2. Query Heatmap
        print("\n[Step 2] Querying heatmap API...")
        res = await client.get(f"{url_base}/heatmap?precision=0.1")
        data = res.json()
        print(f"Heatmap Data: {data}")
        
        # 3. Check for weights
        # With 0.1 precision, both should be in (28.6, 77.2) grid
        found_cluster = any(item.get('weight', 0) >= 2 for item in data)
        
        if found_cluster:
            print("\n🏆 TASK 36 VERIFIED: Heatmap correctly identified incident cluster.")
        else:
            print("\n❌ TASK 36 FAILED: Heatmap did not aggregate incidents correctly.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
