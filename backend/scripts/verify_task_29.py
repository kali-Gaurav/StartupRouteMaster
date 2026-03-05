import httpx
import asyncio
import time

async def verify():
    print("--- 🔄 Task 29: AI False-Positive Feedback Loop Verification ---")
    
    url_base = "http://localhost:8000/api/sos"
    malicious_phone = "+91-9000000000"
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger Initial SOS (should be allowed)
        print(f"\n[Step 1] Triggering initial SOS for {malicious_phone}...")
        payload = {"lat": 28.6139, "lng": 77.2090, "name": "Spammer", "phone": malicious_phone}
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Submit Admin Feedback (Flag as False Positive)
        print("\n[Step 2] Admin flagging event as FALSE POSITIVE...")
        feedback_payload = {
            "is_false_positive": True,
            "correct_category": "spam",
            "notes": "User is testing the button repeatedly."
        }
        res_fb = await client.post(f"{url_base}/{event_id}/feedback", json=feedback_payload)
        print(f"Feedback Status: {res_fb.status_code}")
        
        # 3. Try to trigger again with same phone (Should be BLOCKED by Task 9 Bloom Filter)
        print(f"\n[Step 3] Attempting secondary SOS for {malicious_phone} (Should be blocked)...")
        res_retry = await client.post(f"{url_base}/", json=payload)
        
        print(f"Second SOS Status: {res_retry.status_code}")
        
        if res_fb.status_code == 200 and res_retry.status_code == 403:
            print("\n🏆 TASK 29 VERIFIED: Feedback loop dynamically updated Bloom filter.")
        else:
            print("\n❌ TASK 29 FAILED: Feedback did not block subsequent malicious requests.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
