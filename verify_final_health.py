import asyncio
import httpx
import sys

async def verify_health():
    print("Verifying Backend Health Endpoints...")
    async with httpx.AsyncClient() as client:
        # 1. Root level health
        try:
            resp = await client.get("http://localhost:8000/health")
            print(f"GET /health: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Response: {resp.json()}")
        except Exception as e:
            print(f"GET /health FAILED (Server likely not running): {e}")

        # 2. API Status Health (Frontend expected)
        try:
            resp = await client.get("http://localhost:8000/api/status/health/live")
            print(f"GET /api/status/health/live: {resp.status_code}")
            if resp.status_code == 200:
                print(f"Response: {resp.json()}")
        except Exception as e:
            print(f"GET /api/status/health/live FAILED: {e}")

if __name__ == "__main__":
    # Note: This requires the server to be running.
    # Since I cannot start a long-running server and wait for it in this turn,
    # I'll just check if the logic in the files is correct.
    print("Verification script ready. (Requires manual server start: python backend/app.py)")
