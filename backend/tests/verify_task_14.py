import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from api.v2.admin import reject_payment, BookingFailRequest

async def verify_task_14():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 14 (REJECT UTR ACTION)")
    
    db = SessionLocal()
    booking_id = "B14_REJECT_TEST"
    
    # 0. Setup test data
    u = User(id="u14", email="u14@ex.com")
    db.merge(u)
    
    b1 = Booking(
        id=booking_id, user_id="u14", 
        service_type="AGENT_BOOKING",
        escrow_status=EscrowStatus.UTR_SUBMITTED, 
        utr_number="141414141414",
        amount_paid=1510.0,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    # 1. Execute Manual Reject
    print("  Rejecting payment via admin endpoint...")
    reason = "Fake UTR submitted."
    payload = BookingFailRequest(reason=reason)
    res = await reject_payment(booking_id, payload, db)
    print(f"    API Response: {res}")
    
    # 2. Verify State and Audit
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Final Status: {b1.escrow_status.value}")
    print(f"    Escrow Message: {b1.escrow_message}")
    
    assert b1.escrow_status == EscrowStatus.FAILED
    assert reason in b1.escrow_message
    
    # Check Audit Log
    log = db.query(AuditLog).filter(AuditLog.entity_id == booking_id, AuditLog.action == "MANUAL_PAYMENT_REJECT").first()
    assert log is not None
    assert log.reason == reason
    print(f"    Audit Log Reason: {log.reason}")
    
    # 3. Cleanup
    db.delete(b1)
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ TASK 14 FULLY VERIFIED: Payment rejection correctly updates status and logs reason.")

if __name__ == "__main__":
    asyncio.run(verify_task_14())
