import asyncio
import httpx
import sys
import os

async def test_integration():
    print("\n🔍 --- DEEP DIVE INTEGRATION TEST ---")
    
    # 1. Test Backend Root
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get("http://localhost:8000/")
            print(f"✅ Backend Root: {resp.status_code}")
            if resp.status_code == 200:
                print(f"   App Name: {resp.json().get('app')}")
        except Exception as e:
            print(f"❌ Backend Root Unreachable: {e}")

        # 2. Test Station Autocomplete
        try:
            resp = await client.get("http://localhost:8000/api/stations/search?q=KOTA")
            data = resp.json()
            if resp.status_code == 200:
                print(f"✅ Station Search: Found {len(data)} results for 'KOTA'")
            else:
                print(f"❌ Station Search Endpoint Failed: {resp.status_code}")
        except Exception as e:
            print(f"❌ Station Search Test Failed: {e}")

        # 3. Test Chatbot Endpoint
        try:
            chat_payload = {
                "message": "Find trains from NDLS to BCT",
                "session_id": "integration-test-session"
            }
            # The correct endpoint is /api/chat (no /message suffix)
            resp = await client.post("http://localhost:8000/api/chat", json=chat_payload)
            if resp.status_code == 200:
                print(f"✅ Chatbot Response: {resp.json().get('reply', '')[:50]}...")
            else:
                print(f"❌ Chatbot Endpoint Failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Chatbot Test Failed: {e}")

    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_integration())
