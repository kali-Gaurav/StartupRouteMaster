import asyncio
import httpx
import websockets
import json
import logging
from pprint import pprint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/api/v2"

async def test_e2e_flow():
    print("🚀 Starting E2E Payment & AI Booking Verification...")
    
    # 1. Login to get a token
    # Assuming there's a test user or we can bypass auth for the sake of the test script.
    # Since we can't easily mock auth from outside without knowing the secret, 
    # let's assume we have an endpoint or we can manually trigger the worker locally.
    
    print("⚠️ Since authentication is required for the API, we will test the worker directly to ensure the flow works.")
    from backend.workers.irctc_worker import run_booking_worker
    from backend.database.session import SessionLocal
    from backend.database.models import Booking, User, EscrowStatus
    from datetime import datetime, date
    import uuid
    import sys
    from pathlib import Path
    
    sys.path.append(str(Path("backend").resolve()))
    
    db = SessionLocal()
    
    # Create mock user if none exists
    user = db.query(User).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email="test@routemaster.ai",
            password_hash="mock",
            full_name="Test User",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()

    # Create Mock Booking
    test_booking_id = str(uuid.uuid4())
    booking = Booking(
        id=test_booking_id,
        user_id=user.id,
        pnr_number="PENDING",
        travel_date=date(2026, 3, 10),
        booking_status="pending",
        escrow_status=EscrowStatus.VERIFIED, # Start at verified to trigger worker
        amount_paid=1500.00,
        upi_tx_id="TX_E2E_TEST",
        booking_details={
            "passengers": [
                {"fullName": "Gaurav Nagar", "age": 30, "gender": "M", "berth_preference": "Lower"}
            ],
            "train_number": "12951",
            "boarding_point": "NDLS"
        },
        train_number="12951"
    )
    db.add(booking)
    db.commit()
    
    print(f"✅ Created mock booking {test_booking_id} in VERIFIED state.")
    
    # Simulate Frontend CAPTCHA Submission
    async def simulate_frontend_captcha(booking_id: str):
        from backend.services.multi_layer_cache import multi_layer_cache
        await asyncio.sleep(15) # Wait for worker to reach CAPTCHA phase
        print(f"🖥️ [Frontend Mock] Submitting CAPTCHA for {booking_id}...")
        redis_key = f"captcha:{booking_id}"
        await multi_layer_cache.redis.setex(redis_key, 300, "MOCK_CAPTCHA_123")
        print("🖥️ [Frontend Mock] CAPTCHA submitted!")

    asyncio.create_task(simulate_frontend_captcha(test_booking_id))
    
    # Run worker directly
    print("🤖 Launching AI Ghost Worker...")
    try:
        # Run worker (which uses playwright)
        await run_booking_worker(test_booking_id)
        
        # Verify final state
        db.expire_all()
        updated_booking = db.query(Booking).filter(Booking.id == test_booking_id).first()
        print(f"🏁 Final Escrow Status: {updated_booking.escrow_status.name}")
        print(f"📝 Final Message: {updated_booking.escrow_message}")
        print(f"🎫 PNR: {updated_booking.pnr_number}")
        
        if updated_booking.escrow_status.name == "COMPLETED":
            print("✅ E2E Verification SUCCESSFUL!")
        else:
            print("❌ E2E Verification FAILED!")
            
    except Exception as e:
        print(f"❌ Error during worker execution: {e}")
    finally:
        # Cleanup
        db.delete(booking)
        db.commit()
        db.close()

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path("backend").resolve()))
    asyncio.run(test_e2e_flow())
