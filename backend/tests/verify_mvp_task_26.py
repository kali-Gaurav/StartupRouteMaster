import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus

async def verify_task_26():
    print("\n>>> STARTING VERIFICATION: MVP TASK 26 (STATE MACHINE)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B26_STATE_TEST"
    
    # 0. Setup
    b1 = Booking(
        id=booking_id, user_id="u26", 
        service_type="AGENT_BOOKING", 
        escrow_status=EscrowStatus.CREATED,
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    print(f"  Setup: Booking {booking_id} in CREATED state.")

    # 1. Test Illegal Transition (CREATED -> COMPLETED)
    print("\n[26.1] Attempting illegal transition: CREATED -> COMPLETED...")
    try:
        b1.update_escrow_status(db, EscrowStatus.COMPLETED)
        print("    ❌ FAILURE: Illegal transition allowed!")
        assert False
    except ValueError as e:
        print(f"    ✅ SUCCESS: Caught expected error: {e}")
        assert "not allowed" in str(e)

    # 2. Test Valid Transition (CREATED -> UTR_SUBMITTED)
    print("\n[26.2] Attempting valid transition: CREATED -> UTR_SUBMITTED...")
    b1_active = db.query(Booking).filter(Booking.id == booking_id).first()
    b1_active.update_escrow_status(db, EscrowStatus.UTR_SUBMITTED, performed_by="TEST_USER")
    db.commit()
    
    # Refetch to verify
    b1_final = db.query(Booking).filter(Booking.id == booking_id).first()
    print(f"    Current Status: {b1_final.escrow_status.value}")
    assert b1_final.escrow_status == EscrowStatus.UTR_SUBMITTED
    print("    ✅ SUCCESS: Valid transition processed correctly.")

    # 3. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 26 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_26())
