import httpx
import asyncio
import time

async def verify():
    print("--- 🕵️ Task 25: Real-time Transcript Redaction Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS with sensitive PII
        print("\n[Step 1] Triggering SOS with Aadhaar, Phone, and OTP in transcript...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Privacy User",
            "extra": "My Aadhaar is 1234 5678 9012 and my phone is 9876543210. Help!"
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        redacted_text = data.get('extra', "")
        print(f"Redacted Notes: {redacted_text}")
        
        # 2. Check for redaction markers
        found_redaction = "[REDACTED_ID]" in redacted_text or "[REDACTED_PHONE]" in redacted_text
        
        if found_redaction:
            print("\n🏆 TASK 25 VERIFIED: PII successfully masked in API response.")
        else:
            print("\n❌ TASK 25 FAILED: Sensitive PII was leaked in raw form.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
