import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, UserSession
from api.v2.user import get_my_sessions, revoke_user_session

async def verify_task_35():
    print("\n>>> STARTING VERIFICATION: MVP TASK 35 (SESSION INVALIDATION)")
    
    db = SessionLocal()
    user_id = "u35_test"
    
    # 0. Setup
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    
    u = User(id=user_id, email="u35@ex.com")
    db.add(u)
    db.commit()
    
    # Create 3 mock sessions
    s1 = UserSession(id="S1", user_id=user_id, ip_address="1.1.1.1")
    s2 = UserSession(id="S2", user_id=user_id, ip_address="2.2.2.2")
    s3 = UserSession(id="S3", user_id=user_id, ip_address="3.3.3.3")
    db.add_all([s1, s2, s3])
    db.commit()
    
    print(f"  Setup: Created user {user_id} with 3 sessions.")

    # 1. Test List Sessions (Subtask 35.1)
    print("  Listing sessions...")
    sessions = await get_my_sessions(u, db)
    print(f"    Count: {len(sessions)}")
    assert len(sessions) == 3
    print("    ✅ SUCCESS: All sessions listed.")

    # 2. Test Revoke Session (Subtask 35.2)
    print("\n  Revoking session S2...")
    res = await revoke_user_session("S2", u, db)
    assert res["status"] == "success"
    
    # Verify in DB
    revoked = db.query(UserSession).filter(UserSession.id == "S2").first()
    assert revoked is None
    
    sessions_after = await get_my_sessions(u, db)
    assert len(sessions_after) == 2
    print("    ✅ SUCCESS: Session S2 removed.")

    # 3. Cleanup
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.delete(u)
    db.commit()
    
    print("\n✅ ALL MVP TASK 35 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_35())
