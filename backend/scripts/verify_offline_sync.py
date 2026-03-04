import httpx
import asyncio
import uuid

async def test_offline_sync():
    url = "http://localhost:8000/api/chat"
    session_id = f"test-sync-{uuid.uuid4()}"
    message_id = str(uuid.uuid4())
    
    print("--- Offline Sync & Deduplication Verification ---")
    
    payload = {
        "message": "NDLS to BCT",
        "session_id": session_id,
        "message_id": message_id
    }
    
    # 1. First attempt (Original)
    print(f"\n[Test 1] Sending original message (ID: {message_id})...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"Status: {response.status_code}")
            print(f"Reply: {response.json().get('reply')[:50]}...")
            
            # 2. Second attempt (Simulated re-sync/retry)
            print(f"\n[Test 2] Sending duplicate message (ID: {message_id})...")
            response_dup = await client.post(url, json=payload, timeout=10.0)
            data = response_dup.json()
            print(f"Status: {response_dup.status_code}")
            print(f"State: {data.get('state')}")
            
            if data.get('state') == "duplicate":
                print("[PASS] Backend correctly detected duplicate message ID.")
            else:
                print("[FAIL] Backend processed duplicate message ID.")
                
        except Exception as e:
            print(f"Error: {e}")
            print("Note: Ensure the backend server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_offline_sync())
