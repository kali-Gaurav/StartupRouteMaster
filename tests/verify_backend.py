import httpx
import asyncio
import time

async def test_backend():
    print("--- Verifying Backend Endpoints ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health check
        try:
            resp = await client.get("http://localhost:8000/health")
            print(f"Health: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Health check failed: {e}")

        # 2. Engine Debug
        try:
            resp = await client.get("http://localhost:8000/debug/engine")
            print(f"Debug Engine: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"Debug Engine failed: {e}")

        # 3. Quick Search (NDLS -> BCT)
        try:
            print("Running quick search NDLS -> BCT...")
            resp = await client.get("http://localhost:8000/api/search/quick?source=NDLS&destination=BCT")
            data = resp.json()
            print(f"Search: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Routes found: {data.get('count')}")
                if data.get('count', 0) > 0:
                    first = data['routes'][0]
                    print(f"First route ID: {first.get('route_id')}")
                    print(f"Total Duration: {first.get('total_duration')} mins")
            else:
                print(f"Search error: {data}")
        except Exception as e:
            print(f"Quick Search failed: {e}")

if __name__ == "__main__":
    # Give it a moment to initialize in background
    time.sleep(5)
    asyncio.run(test_backend())
