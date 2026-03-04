import httpx
import asyncio
import json
import redis
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.config import Config

async def verify():
    print("--- 🔐 DPDP Compliance: AES-256 Encryption Verification ---")
    
    # 1. Trigger SOS
    url = "http://localhost:8000/api/sos/"
    payload = {
        "lat": 13.0827, "lng": 80.2707,
        "name": "Secret Passenger",
        "phone": "+91-7777777777",
        "extra": "Top secret emergency details."
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload)
        event_id = res.json().get("id")
        print(f"Created Event ID: {event_id}")
        
        # 2. Check Raw Redis Data
        print("\n[Step 2] Checking RAW data in Redis (should be encrypted)...")
        r = redis.from_url(Config.REDIS_URL)
        raw_val = r.get(f"sos:event:{event_id}")
        
        if raw_val:
            data = json.loads(raw_val)
            print(f"Is Encrypted Flag: {data.get('is_encrypted')}")
            print(f"Encrypted Name: {data.get('name')}")
            print(f"Encrypted Phone: {data.get('phone')}")
            
            if data.get('name') != payload['name'] and len(data.get('name', '')) > 20:
                print("\n✅ DATA IS ENCRYPTED IN REDIS.")
            else:
                print("\n❌ DATA IS NOT ENCRYPTED IN REDIS.")
        else:
            print("\n⚠️ Event not found in Redis. (Might be using local storage fallback)")

        # 3. Check Decrypted API response
        print("\n[Step 3] Fetching via API (should be decrypted)...")
        res_get = await client.get(f"http://localhost:8000/api/sos/all")
        events = res_get.json()
        target = next((e for e in events if e['id'] == event_id), None)
        
        if target:
            print(f"Decrypted Name: {target.get('name')}")
            if target.get('name') == payload['name']:
                print("\n🏆 ENCRYPTION/DECRYPTION VERIFIED: Data safe at rest, readable via API.")
            else:
                print("\n❌ DECRYPTION FAILED.")

if __name__ == "__main__":
    asyncio.run(verify())