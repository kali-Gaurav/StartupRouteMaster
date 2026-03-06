import sys
import os
import asyncio
import uuid
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal
from database.models import PaymentSession, Booking, User
from services.session_lock_service import SessionLockService
from services.cache_service import cache_service

async def verify_task_7():
    print("=== Verifying Task 7: Session Lock & Heartbeats ===")
    
    db = SessionLocal()
    lock_service = SessionLockService(db)
    
    try:
        user_id = str(uuid.uuid4())
        session_code = "TEST77"
        booking_id = str(uuid.uuid4())
        
        # Setup mock DB records
        user = User(id=user_id, email=f"test7_{user_id}@example.com")
        db.add(user)
        db.commit()
        
        booking = Booking(id=booking_id, user_id=user_id, amount_paid=100.0, booking_status="pending", booking_details={})
        payment_session = PaymentSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_code=session_code,
            amount=100.0,
            status="PENDING"
        )
        db.add_all([booking, payment_session])
        db.commit()

        # 1. Test Lock Initialization
        print("Testing Lock Initialization...")
        lock_service.initialize_lock(session_code, user_id, booking_id=booking_id)
        assert cache_service.get(f"payment_session_lock:{session_code}")["status"] == "ACTIVE"
        assert cache_service.get(f"payment_heartbeat:{session_code}") is not None
        print("[OK] Lock and Heartbeat initialized")

        # 2. Test Heartbeat Ping
        print("Testing Heartbeat Ping...")
        time.sleep(1) # Let time pass
        hb1 = cache_service.get(f"payment_heartbeat:{session_code}")
        
        # Call record_heartbeat (endpoint logic)
        is_active = lock_service.record_heartbeat(session_code)
        assert is_active is True
        
        hb2 = cache_service.get(f"payment_heartbeat:{session_code}")
        assert hb1 != hb2 # Timestamp should have updated
        print("[OK] Heartbeat ping correctly refreshes TTL")

        # 3. Test Auto-Cancel on Lost Heartbeat
        print("Testing Auto-Cancel on Idle...")
        # Simulate lost heartbeat by deleting it from Redis
        cache_service.delete(f"payment_heartbeat:{session_code}")
        
        # Run background checker
        expired = await lock_service.check_and_cancel_idle_sessions(session_code)
        assert expired is True
        
        # Verify DB states changed
        db.refresh(payment_session)
        db.refresh(booking)
        
        assert payment_session.status == "EXPIRED"
        assert booking.booking_status == "cancelled"
        assert "abandoned" in booking.escrow_message
        
        # Verify cache was cleaned up
        assert cache_service.get(f"payment_session_lock:{session_code}") is None
        print("[OK] Idle session successfully auto-cancelled")

    finally:
        db.close()

    print("=== Task 7 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_7())
