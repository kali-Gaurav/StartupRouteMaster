import asyncio
import httpx
import os
import sys

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app

async def verify_system():
    print("🧪 Starting System Verification...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test Unified Search
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15"
        }
        print("📡 Testing Unified Search...")
        response = await client.post("/api/v2/search/unified", json=payload)
        
        if response.status_code != 200:
            print(f"❌ Unified Search Failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        if not isinstance(data, list):
            print(f"❌ Invalid Response Type: Expected list, got {type(data)}")
            return False
            
        print(f"✅ Unified Search Success! Found {len(data)} journeys.")
        
        # 2. Test Autocomplete
        print("📡 Testing Autocomplete...")
        response = await client.get("/api/stations/suggest?q=del")
        if response.status_code == 200:
            print(f"✅ Autocomplete Success! Found {len(response.json())} stations.")
        else:
            print(f"❌ Autocomplete Failed: {response.status_code}")
            return False

    print("🏁 Verification Complete: SYSTEM IS STABLE.")
    return True

if __name__ == "__main__":
    success = asyncio.run(verify_system())
    if not success:
        sys.exit(1)
