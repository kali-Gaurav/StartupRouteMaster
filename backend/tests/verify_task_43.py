import httpx
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from database.models import User, Booking, PaymentSession, AuditLog
from services.unlock_service import UnlockService

async def verify_task_43():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 43 (PAYMENT WEBHOOK)")
    
    db = SessionLocal()
    user_id = "test-user-43"
    route_id = "T12625_WEBHOOK_TEST"
    
    # 0. Setup User
    test_user = User(id=user_id, email="test43@example.com", full_name="Test User 43")
    db.merge(test_user)
    db.commit()
    
    # 1. Initiate Unlock (Creates Booking + PaymentSession)
    print("  Initiating Unlock Request...")
    booking = UnlockService.create_unlock_request(db, user_id, route_id)
    pay_session = db.query(PaymentSession).filter(PaymentSession.user_id == user_id, PaymentSession.route_id == route_id).first()
    
    print(f"    Booking ID: {booking.id}")
    print(f"    Session Code: {pay_session.session_code}")
    
    # 2. Simulate Webhook Call
    print("\n  Simulating External Webhook Notification...")
    # We'll use httpx to call the local endpoint if running, or just call the handler function.
    # To be safe in this environment, we'll import and call the handler.
    from api.v2.webhooks import payment_webhook_handler, PaymentWebhook
    
    payload = PaymentWebhook(
        utr_number="UTR123456789",
        amount=49.0,
        session_code=pay_session.session_code,
        status="SUCCESS"
    )
    
    # Mocking DB for the handler call
    await payment_webhook_handler(payload, db)
    
    # 3. Verify Result
    print("\n  Verifying Automatic Unlock...")
    db.refresh(booking)
    print(f"    Booking Unlocked: {booking.is_unlocked}")
    print(f"    Escrow Status: {booking.escrow_status.value}")
    
    assert booking.is_unlocked == True
    assert booking.escrow_status.value == "COMPLETED"
    assert booking.utr_number == "UTR123456789"
    
    # 4. Cleanup
    db.delete(pay_session)
    db.delete(booking)
    db.query(AuditLog).filter(AuditLog.entity_id == booking.id).delete()
    db.commit()
    
    print("\n✅ TASK 43 FULLY VERIFIED: Webhook auto-fulfillment is functional.")

if __name__ == "__main__":
    asyncio.run(verify_task_43())
