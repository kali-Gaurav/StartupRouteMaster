import asyncio
import sys
import os
from database.session import SessionLocal
from database.models import User, AuditLog
from api.v2.agent import toggle_agent_availability

async def verify_task_30():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 30 (AGENT AVAILABILITY)")
    
    db = SessionLocal()
    agent_id = "agent30"
    
    # 0. Setup
    u = User(id=agent_id, email="a30@ex.com", role="agent", is_available=False)
    db.merge(u)
    db.commit()
    print(f"  Initial State: Available=False")
    
    # 1. Toggle Online
    print("  Toggling agent ONLINE...")
    res1 = await toggle_agent_availability(agent_id, db)
    assert res1["is_available"] == True
    
    # Verify DB
    u = db.query(User).filter(User.id == agent_id).first()
    assert u.is_available == True
    assert u.last_heartbeat is not None
    print("    DB state updated successfully.")
    
    # 2. Check Audit Log
    log = db.query(AuditLog).filter(
        AuditLog.entity_id == agent_id, 
        AuditLog.action == "SHIFT_START"
    ).first()
    assert log is not None
    print(f"    Audit Log: OK (Action={log.action})")
    
    # 3. Toggle Offline
    print("  Toggling agent OFFLINE...")
    res2 = await toggle_agent_availability(agent_id, db)
    assert res2["is_available"] == False
    
    # 4. Cleanup
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    db.query(AuditLog).filter(AuditLog.entity_id == agent_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == agent_id).delete(synchronize_session=False)
    db.commit()
    
    print("\n✅ TASK 30 FULLY VERIFIED: Agent availability toggle and shift logging are operational.")

if __name__ == "__main__":
    asyncio.run(verify_task_30())
