import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, BankTransaction, AuditLog
from api.v2.webhooks import payment_webhook_handler, PaymentWebhook

async def verify_task_21():
    print("\n>>> STARTING VERIFICATION: MVP TASK 21 (IDEMPOTENCY)")
    
    db = SessionLocal()
    booking_id = "B21_IDEM_TEST"
    event_id = "EV_UNIQUE_123"
    utr = "123456789012"
    
    # 0. Setup
    u = User(id="u21", email="u21@ex.com")
    db.merge(u)
    
    b1 = Booking(
        id=booking_id, user_id="u21", 
        service_type="AGENT_BOOKING", 
        escrow_status=EscrowStatus.CREATED,
        booking_details={}
    )
    db.merge(b1)
    
    # Clear any old test data
    db.query(BankTransaction).filter(BankTransaction.event_id == event_id).delete()
    db.commit()
    
    payload = PaymentWebhook(
        utr_number=utr,
        amount=100.0,
        event_id=event_id,
        booking_id=booking_id
    )

    # 1. First Call: Should succeed
    print("  Executing first webhook call...")
    res1 = await payment_webhook_handler(payload, db)
    
    print(f"    Res 1: {res1.get('message')}")
    assert res1.get("message") == "Payment processed successfully."
    
    # Check DB
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    assert b1.escrow_status == EscrowStatus.VERIFIED
    
    tx = db.query(BankTransaction).filter(BankTransaction.event_id == event_id).first()
    assert tx is not None
    assert tx.status == "PROCESSED"
    print("    SUCCESS: First call processed correctly.")

    # 2. Second Call (Replay): Should be blocked
    print("\n  Executing second (replay) webhook call...")
    res2 = await payment_webhook_handler(payload, db)
    
    print(f"    Res 2: {res2.get('message')}")
    assert res2.get("is_replay") is True
    assert res2.get("message") == "Already processed."
    
    # Verify no duplicate transaction entries
    tx_count = db.query(BankTransaction).filter(BankTransaction.event_id == event_id).count()
    assert tx_count == 1
    print("    SUCCESS: Replay blocked by idempotency logic.")

    # 3. Cleanup
    db.delete(tx)
    db.delete(b1)
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 21 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_21())
