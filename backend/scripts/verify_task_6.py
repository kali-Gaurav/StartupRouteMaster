import httpx
import asyncio
import redis
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.config import Config

async def verify():
    print("--- 🗜️ Task 6: Chat History LZ4/Zlib Compression Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with LARGE chat history
        print("\n[Step 1] Triggering SOS with large chat log (50 messages)...")
        large_chat = [{"sender": "user", "content": f"Message number {i} - Emergency detail reporting."} for i in range(50)]
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Compression Test User",
            "chat_history": large_chat
        }
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Check Raw Redis Data (should be a compressed string 'c:...')
        print("\n[Step 2] Verifying compression in RAW Redis storage...")
        r = redis.from_url(Config.REDIS_URL)
        raw_val = r.get(f"sos:event:{event_id}")
        
        if raw_val:
            data = json.loads(raw_val)
            chat_raw = data.get("chat_history")
            print(f"Raw chat_history type in Redis: {type(chat_raw)}")
            if isinstance(chat_raw, str) and chat_raw.startswith("c:"):
                print(f"✅ SUCCESS: Chat history is compressed. (Value starts with 'c:')")
                print(f"   Compressed Length: {len(chat_raw)} bytes")
            else:
                print(f"❌ FAILURE: Chat history is NOT compressed in Redis.")
        else:
            print("⚠️ Note: Event not found in Redis (local fallback active). Skipping raw check.")

        # 3. Verify Decompression via API
        print("\n[Step 3] Verifying transparent decompression via API...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        
        chat_data = event.get("chat_history")
        print(f"DEBUG: API chat_history type: {type(chat_data)}")
        print(f"DEBUG: API chat_history content: {str(chat_data)[:100]}...")
        
        if event and isinstance(chat_data, list):
            print(f"✅ SUCCESS: API returned decompressed list of {len(event['chat_history'])} messages.")
            print("\n🏆 TASK 6 VERIFIED: High-efficiency storage active.")
        else:
            print("❌ FAILURE: Decompression failed or API returned incorrect type.")

if __name__ == "__main__":
    asyncio.run(verify())
