import asyncio
import sys
import os
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import User, AdminSession
from api.v2.admin import get_session_history

async def verify_task_15():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 15 (SESSION HISTORY)")
    
    db = SessionLocal()
    session_id = "S15_TEST"
    
    # 0. Setup test data
    u = User(id="admin15", email="a15@ex.com", role="admin")
    db.merge(u)
    
    now = datetime.utcnow()
    # 1 hour session
    s1 = AdminSession(
        id=session_id, admin_id="admin15", 
        created_at=now - timedelta(hours=1),
        expires_at=now,
        is_revoked=False
    )
    db.merge(s1)
    db.commit()
    
    # 1. Fetch History
    print("  Fetching session history...")
    history = await get_session_history(db=db)
    
    # 2. Verify Logic
    matching = [s for s in history if s["id"] == session_id]
    assert len(matching) > 0
    
    s = matching[0]
    print(f"    Session ID: {s['id']}")
    print(f"    Duration Mins: {s['duration_mins']}")
    
    assert s["duration_mins"] == 60.0
    
    # 3. Cleanup
    db.query(AdminSession).filter(AdminSession.id == session_id).delete()
    db.commit()
    
    print("\n✅ TASK 15 FULLY VERIFIED: Admin session history accurately calculates durations.")

if __name__ == "__main__":
    asyncio.run(verify_task_15())
