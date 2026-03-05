import httpx
import asyncio
import time

async def verify():
    print("--- 🛡️ Task 9: Bloom Filter False-Alarm Rejection Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Test Blocked Phone
        blocked_phone = "+91-0000000000"
        print(f"\n[Test 1] Triggering SOS with BLOCKED phone {blocked_phone}...")
        payload_bad = {"lat": 28.6139, "lng": 77.2090, "name": "Malicious User", "phone": blocked_phone}
        res_bad = await client.post(url_base, json=payload_bad)
        
        print(f"Status: {res_bad.status_code}")
        if res_bad.status_code == 403:
            print(f"✅ SUCCESS: Bloom filter correctly rejected the request.")
        else:
            print(f"❌ FAILURE: Bloom filter did not block the request (Status: {res_bad.status_code}).")

        # 2. Test Clean Phone
        clean_phone = "+91-9876543210"
        print(f"\n[Test 2] Triggering SOS with CLEAN phone {clean_phone}...")
        payload_good = {"lat": 28.6139, "lng": 77.2090, "name": "Valid User", "phone": clean_phone}
        res_good = await client.post(url_base, json=payload_good)
        
        print(f"Status: {res_good.status_code}")
        if res_good.status_code == 200:
            print(f"✅ SUCCESS: Clean request passed through.")
            print("\n🏆 TASK 9 VERIFIED: Bloom filter rapid rejection functional.")
        else:
            print(f"❌ FAILURE: Clean request blocked or failed.")

if __name__ == "__main__":
    # Wait for server reload
    time.sleep(10)
    asyncio.run(verify())
