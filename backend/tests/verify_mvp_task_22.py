import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus, PaymentSession
from api.v2.booking import regenerate_payment
from unittest.mock import MagicMock

async def verify_task_22():
    print("\n>>> STARTING VERIFICATION: MVP TASK 22 (QR REGENERATION)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    booking_id = "B22_REGEN_TEST"
    user_id = "u22"
    
    # 0. Setup
    db.query(User).filter(User.email == "u22@ex.com").delete()
    db.commit()
    
    u = User(id=user_id, email="u22@ex.com")
    db.add(u)
    
    b1 = Booking(
        id=booking_id, user_id=user_id, 
        service_type="UNLOCK", 
        escrow_status=EscrowStatus.CREATED,
        amount_paid=49.0,
        merchant_vpa="old_vpa@upi",
        booking_details={}
    )
    db.merge(b1)
    
    # Clear old sessions
    db.query(PaymentSession).filter(PaymentSession.booking_id == booking_id).delete()
    db.commit()
    
    print(f"  Setup: Booking {booking_id} with VPA 'old_vpa@upi'.")

    # 1. Execute Regeneration
    print("  Executing regenerate_payment call...")
    # Mock current user for dependency
    mock_user = u
    res = await regenerate_payment(booking_id, db, mock_user)
    
    print(f"    Status: {res.get('status')}")
    print(f"    New VPA: {res.get('vpa')}")
    print(f"    New UPI URL: {res.get('upi_url')}")
    
    # 2. Assertions
    assert res.get("status") == "success"
    assert res.get("vpa") != "old_vpa@upi"
    assert "upi://pay" in res.get("upi_url")
    
    # Check DB
    b1 = db.query(Booking).filter(Booking.id == booking_id).first()
    assert b1.merchant_vpa == res.get("vpa")
    
    session = db.query(PaymentSession).filter(PaymentSession.booking_id == booking_id).first()
    assert session is not None
    assert session.amount == 49.0
    print(f"    SUCCESS: New session {session.session_code} recorded in DB.")

    # 3. Cleanup
    db.delete(session)
    db.delete(b1)
    db.commit()
    
    print("\n✅ ALL MVP TASK 22 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_22())
