import asyncio
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.session import SessionLocal
from database.models import User, UserSession, AuditLog
from core.auth.auth_manager import AuthManager
from api.dependencies import get_current_user

async def setup_mock_db():
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    # Cleanup
    db.query(UserSession).filter(UserSession.user_id == "faang_test_user").delete()
    db.query(AuditLog).filter(AuditLog.entity_id == "faang_test_user").delete()
    db.query(User).filter(User.id == "faang_test_user").delete()
    db.commit()
    
    return db

async def test_faang_session_control():
    print("\n>>> STARTING VERIFICATION: FAANG-LEVEL AUTH (SESSION CONTROL)")
    db = await setup_mock_db()
    
    try:
        # 1. Create a dummy user
        user = User(id="faang_test_user", email="faang@test.com", firebase_uid="faang_sb_123")
        db.add(user)
        db.commit()
        
        auth_manager = AuthManager(db)
        
        # 2. Simulate Login from Device A (Laptop)
        mock_request_A = MagicMock()
        mock_request_A.headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "x-forwarded-for": "192.168.1.100"}
        mock_request_A.client.host = "192.168.1.100"
        
        session_A = auth_manager.track_session(user, mock_request_A, refresh_token="refresh_token_A")
        print(f"  ✅ Logged in from Laptop: Session ID {session_A.id}")
        assert session_A.device_info["type"] == "Desktop"
        
        # 3. Simulate Login from Device B (Mobile)
        mock_request_B = MagicMock()
        mock_request_B.headers = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)", "x-forwarded-for": "10.0.0.50"}
        mock_request_B.client.host = "10.0.0.50"
        
        # Mocking time change
        session_B = auth_manager.track_session(user, mock_request_B, refresh_token="refresh_token_B")
        print(f"  ✅ Logged in from Mobile: Session ID {session_B.id}")
        assert session_B.device_info["type"] == "Mobile"
        
        # 4. Get Active Sessions
        active_sessions = auth_manager.get_active_sessions(user.id)
        print(f"  Active Sessions Count: {len(active_sessions)}")
        assert len(active_sessions) == 2
        
        # 5. Revoke Session A (Logout from Laptop)
        revoked = auth_manager.revoke_session(session_A.id, user.id)
        assert revoked == True
        print(f"  ✅ Revoked Laptop Session")
        
        # 6. Verify only Mobile session is active
        active_sessions = auth_manager.get_active_sessions(user.id)
        assert len(active_sessions) == 1
        assert active_sessions[0].id == session_B.id
        print("  ✅ Session control isolation verified")
        
        # 7. Revoke All Sessions (Global Logout)
        count = auth_manager.revoke_all_sessions(user.id)
        assert count == 1
        active_sessions = auth_manager.get_active_sessions(user.id)
        assert len(active_sessions) == 0
        print("  ✅ Global Logout verified")
        
        # 8. Check Audit Logs
        logs = db.query(AuditLog).filter(AuditLog.entity_id == user.id).all()
        print(f"  Audit Logs Generated: {len(logs)}")
        actions = [log.action for log in logs]
        assert "SESSION_CREATED" in actions
        assert "SESSION_REVOKED" in actions
        assert "ALL_SESSIONS_REVOKED" in actions
        print("  ✅ Audit Logging verified")
        
        print("\n🎉 FAANG-LEVEL SESSION CONTROL VALIDATED!")
        
    finally:
        # Cleanup
        db.query(UserSession).filter(UserSession.user_id == "faang_test_user").delete()
        db.query(AuditLog).filter(AuditLog.entity_id == "faang_test_user").delete()
        db.query(User).filter(User.id == "faang_test_user").delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    asyncio.run(test_faang_session_control())
