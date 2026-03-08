import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, BankTransaction
from api.v2.webhooks import payment_webhook_handler, PaymentWebhook
from utils.payments import standardize_utr

async def verify_task_24():
    print("\n>>> STARTING VERIFICATION: MVP TASK 24 (FUZZY UTR MATCHING)")
    
    # 1. Test Utility Directly
    print("\n[24.1] Testing standardize_utr utility...")
    messy_utr = "  123O567I901L  "
    clean_utr = standardize_utr(messy_utr)
    print(f"    Messy: '{messy_utr}' -> Clean: '{clean_utr}'")
    assert clean_utr == "123056719011"
    print("    SUCCESS: Replacement and stripping verified.")

    # 2. Test Webhook with messy UTR
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B24_FUZZY_TEST"
    user_id = "u24"
    
    # Setup
    db.query(BankTransaction).filter(BankTransaction.utr_number == "123056719011").delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    u = User(id=user_id, email="u24@ex.com")
    db.add(u)
    
    b1 = Booking(
        id=booking_id, user_id=user_id, service_type="UNLOCK", 
        escrow_status=EscrowStatus.CREATED, amount_paid=49.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    print("\n[24.3] Executing webhook with messy UTR...")
    payload = PaymentWebhook(
        utr_number=" 123O567I901L ",
        amount=49.0,
        booking_id=booking_id
    )
    
    res = await payment_webhook_handler(payload, db)
    assert res.get("status") == "accepted"
    
    # Verify DB has CLEAN UTR
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Booking UTR in DB: {b1.utr_number}")
    assert b1.utr_number == "123056719011"
    assert b1.escrow_status == EscrowStatus.COMPLETED # UNLOCK auto-completes
    print("    SUCCESS: Webhook correctly standardized and matched messy UTR.")

    # 3. Cleanup
    db.query(BankTransaction).filter(BankTransaction.utr_number == "123056719011").delete()
    db.delete(b1)
    db.delete(u)
    db.commit()
    
    print("\n✅ ALL MVP TASK 24 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_24())
