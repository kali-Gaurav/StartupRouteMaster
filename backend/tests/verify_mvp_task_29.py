import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, Booking, EscrowStatus
from api.v2.user import get_active_payment_session

async def verify_task_29():
    print("\n>>> STARTING VERIFICATION: MVP TASK 29 (SESSION RECOVERY)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    user_id = "u29"
    booking_id = "B29_RECOVERY_TEST"
    
    # 0. Setup
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    u = User(id=user_id, email="u29@ex.com")
    db.add(u)
    
    b1 = Booking(
        id=booking_id, user_id=user_id, 
        service_type="UNLOCK", 
        escrow_status=EscrowStatus.CREATED,
        amount_paid=49.42,
        merchant_vpa="test@upi",
        booking_details={}
    )
    db.merge(b1)
    db.commit()
    
    print(f"  Setup: Created pending booking {booking_id} for user {user_id}.")

    # 1. Execute Recovery API
    print("  Executing get_active_payment_session call...")
    res = await get_active_payment_session(u, db)
    
    print(f"    Has Active: {res.get('has_active')}")
    print(f"    Found Booking ID: {res.get('booking_id')}")
    
    # 2. Assertions
    assert res.get("has_active") is True
    assert res.get("booking_id") == booking_id
    assert res.get("amount") == 49.42
    assert res.get("vpa") == "test@upi"
    
    print("    ✅ SUCCESS: Pending session correctly detected.")

    # 3. Cleanup
    db.query(Booking).filter(Booking.id == booking_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 29 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_29())
