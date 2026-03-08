import asyncio
import aiohttp
import hmac
import hashlib
import json
import sys
import os
from datetime import datetime, timedelta

# [FULL SYSTEM VERIFICATION]
# This script tests the entire integrated flow: Search -> Initiate -> Pay -> Verify

BASE_URL = "http://127.0.0.1:8000"
SECRET_KEY = "RM_LOCAL_SECRET_KEY" # Standardized secret for dev tests

async def test_full_flow():
    print("\n🚀 STARTING FULL SYSTEM INTEGRATION TEST...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Search Flow (Task 1, 9, 17)
        print("\n[1] Testing Search (NDLS -> KOTA)...")
        search_params = {
            "source": "NDLS",
            "destination": "KOTA",
            "date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
            "quota": "GN"
        }
        async with session.get(f"{BASE_URL}/api/v2/search/unified", params=search_params) as resp:
            assert resp.status == 200
            data = await resp.json()
            print(f"    Found {len(data['data']['journeys'])} journeys.")
            journey_id = data['data']['journeys'][0]['journey_id']
            session_id = data['session_id']
            print(f"    Selected Journey: {journey_id}")

        # 2. Initiate UNLOCK (Task 25, 26)
        print("\n[2] Initiating UNLOCK request...")
        init_params = {
            "journey_id": journey_id,
            "service_type": "UNLOCK",
            "user_id": "u_test_system"
        }
        # Note: In production this needs Auth, but for system verify we test the endpoint
        async with session.post(f"{BASE_URL}/api/v2/booking/initiate", params=init_params) as resp:
            if resp.status != 200:
                print(f"    Failed: {await resp.text()}")
                assert False
            init_data = await resp.json()
            booking_id = init_data['id']
            amount = init_data['amount']
            print(f"    Booking Created: {booking_id} (Amount: ₹{amount})")

        # 3. Webhook Payment Simulation (Task 21, 28, 30)
        print("\n[3] Simulating Secured Payment Webhook...")
        utr = "112233445566"
        webhook_payload = {
            "utr_number": utr,
            "amount": amount,
            "booking_id": booking_id,
            "event_id": f"evt_{booking_id}"
        }
        body_bytes = json.dumps(webhook_payload, separators=(',', ':')).encode()
        
        # [30] Sign the payload
        signature = hmac.new(SECRET_KEY.encode(), body_bytes, hashlib.sha256).hexdigest()
        
        headers = {
            "X-RM-Signature": signature,
            "Content-Type": "application/json",
            "X-Forwarded-For": "127.0.0.1" # [28] Whitelist
        }
        
        async with session.post(f"{BASE_URL}/api/v2/webhooks/payment-simulate", data=body_bytes, headers=headers) as resp:
            res_hook = await resp.json()
            print(f"    Webhook Status: {resp.status} - {res_hook.get('message')}")
            assert resp.status == 200
            assert res_hook.get("status") == "accepted"

        # 4. Final Verification
        print("\n[4] Verifying Final Booking State...")
        # Since UNLOCK auto-completes in mock logic
        from database.session import SessionLocal
        from database.models import Booking, EscrowStatus
        db = SessionLocal()
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        print(f"    Final Status in DB: {booking.escrow_status.value}")
        assert booking.escrow_status == EscrowStatus.COMPLETED
        print("    ✅ SUCCESS: Full flow verified.")

        # Cleanup
        db.delete(booking)
        db.commit()
        db.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_full_flow())
        print("\n⭐ ALL SYSTEM INTEGRATION TESTS PASSED PERFECTLY!")
    except Exception as e:
        print(f"\n❌ SYSTEM TEST FAILED: {e}")
        sys.exit(1)
