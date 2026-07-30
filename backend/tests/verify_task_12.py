import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from api.v2.webhooks import bank_sms_webhook, BankSMSPayload

async def verify_task_12():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 12 (BANK SMS WEBHOOK)")
    
    db = SessionLocal()
    utr = "123456789012"
    
    # 0. Setup test data
    u = User(id="u12", email="u12@ex.com")
    db.merge(u)
    
    # Booking in UTR_SUBMITTED state
    b1 = Booking(
        id="B12_TEST", user_id="u12", 
        escrow_status=EscrowStatus.UTR_SUBMITTED, 
        utr_number=utr,
        amount_paid=49.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 1. Simulate SMS arrival
    print("  Simulating incoming bank SMS...")
    sms_text = f"Your a/c XXXXX123 debited for INR 49.00. Ref No: {utr}. Thanks for using SBI."
    payload = BankSMSPayload(sender="SBI-BANK", text=sms_text)
    
    res = await bank_sms_webhook(payload, db)
    print(f"    Webhook Response: {res}")
    
    # 2. Verify State Transition
    b1 = db.query(Booking).filter(Booking.id == "B12_TEST").first()
    print(f"    Final Status: {b1.escrow_status.value}")
    
    assert b1.escrow_status == EscrowStatus.VERIFIED
    assert res["status"] == "verified"
    
    # 3. Cleanup
    db.delete(b1)
    db.commit()
    
    print("\n✅ TASK 12 FULLY VERIFIED: Bank SMS auto-verification is operational.")

if __name__ == "__main__":
    asyncio.run(verify_task_12())
