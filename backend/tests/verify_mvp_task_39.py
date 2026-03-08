import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, AuditLog
from api.v2.admin import revert_payment_rejection

async def verify_task_39():
    print("\n>>> STARTING VERIFICATION: MVP TASK 39 (ADMIN REVERSION)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B39_REVERT_TEST"
    
    # 0. Setup: Create a FAILED booking
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.commit()
    
    b1 = Booking(
        id=booking_id, user_id="u39", service_type="UNLOCK", 
        escrow_status=EscrowStatus.FAILED, 
        escrow_message="Rejected by mistake",
        booking_details={}
    )
    db.add(b1)
    db.commit()
    print(f"  Setup: Created FAILED booking {booking_id}.")

    # 1. Execute Reversion
    print("  Executing revert_payment_rejection call...")
    res = await revert_payment_rejection(booking_id, db)
    assert res["success"] is True
    
    # 2. Verify State
    db.refresh(b1)
    print(f"    New Status: {b1.escrow_status.value}")
    print(f"    New Message: {b1.escrow_message}")
    
    assert b1.escrow_status == EscrowStatus.UTR_SUBMITTED
    assert "reverted" in b1.escrow_message
    print("    ✅ SUCCESS: Booking restored to UTR_SUBMITTED.")

    # 3. Verify Audit Log
    log = db.query(AuditLog).filter(
        AuditLog.entity_id == booking_id,
        AuditLog.action == "MANUAL_REJECTION_REVERT"
    ).first()
    assert log is not None
    print(f"    Audit Entry: {log.action} by {log.performed_by}")
    print("    ✅ SUCCESS: Reversion audited.")

    # 4. Cleanup
    db.delete(b1)
    db.query(AuditLog).filter(AuditLog.entity_id == booking_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 39 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_39())
