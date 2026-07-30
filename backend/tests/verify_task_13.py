import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from api.v2.admin import verify_payment

async def verify_task_13():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 13 (MARK AS PAID ACTION)")
    
    db = SessionLocal()
    booking_id = "B13_VERIFY_TEST"
    
    # 0. Setup test data (UNLOCK type)
    u = User(id="u13", email="u13@ex.com")
    db.merge(u)
    
    b1 = Booking(
        id=booking_id, user_id="u13", 
        service_type="UNLOCK",
        escrow_status=EscrowStatus.UTR_SUBMITTED, 
        utr_number="131313131313",
        amount_paid=49.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 1. Execute Manual Verify
    print("  Executing manual verify action via admin endpoint...")
    res = await verify_payment(booking_id, db)
    print(f"    API Response: {res}")
    
    # 2. Verify State and Side Effects
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Final Status: {b1.escrow_status.value}")
    print(f"    Is Unlocked: {b1.is_unlocked}")
    
    assert b1.escrow_status == EscrowStatus.COMPLETED # Auto-completed for UNLOCK
    assert b1.is_unlocked == True
    
    # Check Audit Log
    log = db.query(AuditLog).filter(AuditLog.entity_id == booking_id, AuditLog.action == "MANUAL_PAYMENT_VERIFY").first()
    assert log is not None
    print(f"    Audit Log: OK (Performed by {log.performed_by})")
    
    # 3. Cleanup
    db.delete(b1)
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ TASK 13 FULLY VERIFIED: Manual 'Mark as Paid' correctly updates state and unlocks access.")

if __name__ == "__main__":
    asyncio.run(verify_task_13())
