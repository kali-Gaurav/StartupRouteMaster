import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, UserSession, RouteSearchLog, Booking, Profile
from api.v2.user import delete_user_account
from datetime import datetime

async def verify_task_37():
    print("\n>>> STARTING VERIFICATION: MVP TASK 37 (GDPR DELETION)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    user_id = "u37_del_test"
    
    # 0. Setup test data
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    u = User(id=user_id, email="u37@ex.com")
    p = Profile(user_id=user_id, id="sb_37", name="Delete Me")
    s = UserSession(user_id=user_id, ip_address="1.1.1.1")
    l = RouteSearchLog(user_id=user_id, src="NDLS", dst="BOM", date=datetime.now().date(), latency_ms=100.0)
    b = Booking(id="B37", user_id=user_id, service_type="UNLOCK", booking_details={})
    
    db.add_all([u, p, s, l, b])
    db.commit()
    print(f"  Setup: Created user {user_id} with Profile, Session, Log, and Booking.")

    # 1. Execute Deletion
    print("  Executing account deletion...")
    res = await delete_user_account(u, db)
    assert res["status"] == "success"
    
    # 2. Verify Deletions
    print("  Verifying data wipe...")
    assert db.query(User).filter(User.id == user_id).first() is None
    assert db.query(Profile).filter(Profile.user_id == user_id).first() is None
    assert db.query(UserSession).filter(UserSession.user_id == user_id).first() is None
    assert db.query(RouteSearchLog).filter(RouteSearchLog.user_id == user_id).first() is None
    print("    ✅ SUCCESS: User, Profile, Sessions, and Logs wiped.")

    # 3. Verify Anonymization
    print("  Verifying booking anonymization...")
    booking_after = db.query(Booking).filter(Booking.id == "B37").first()
    assert booking_after is not None
    assert booking_after.user_id is None
    print(f"    Booking user_id after deletion: {booking_after.user_id}")
    print("    ✅ SUCCESS: Booking anonymized (user_id=None).")

    # 4. Cleanup
    db.delete(booking_after)
    db.commit()
    
    print("\n✅ ALL MVP TASK 37 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_37())
