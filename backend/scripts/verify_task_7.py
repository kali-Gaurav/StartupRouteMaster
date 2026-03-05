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
    print("--- 🌊 Task 7: High-Priority SOS Redis Stream Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    stream_key = "sos:stream:priority"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS
        print("\n[Step 1] Triggering SOS...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Stream Test User",
            "extra": "Testing Task 7 Redis Streams"
        }
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Check Redis Stream using XREAD
        print(f"\n[Step 2] Reading from Redis Stream '{stream_key}'...")
        r = redis.from_url(Config.REDIS_URL)
        
        # Read the last message from the stream
        messages = r.xread({stream_key: 0}, count=5)
        
        found = False
        if messages:
            for stream, msgs in messages:
                for msg_id, data in msgs:
                    # Redis stream data is returned as bytes
                    stored_eid = data.get(b'event_id').decode('utf-8')
                    if stored_eid == event_id:
                        found = True
                        print(f"✅ SUCCESS: Found event {event_id} in Redis Stream.")
                        print(f"   Stream Message ID: {msg_id.decode('utf-8')}")
                        print(f"   Priority: {data.get(b'priority').decode('utf-8')}")
                        break
        
        if found:
            print("\n🏆 TASK 7 VERIFIED: Safety events are now persistent and replayable in Redis Streams.")
        else:
            print("\n❌ TASK 7 FAILED: Event not found in the stream. Check if Redis is enabled.")

if __name__ == "__main__":
    asyncio.run(verify())
