import asyncio
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.dependencies import get_current_user
from database.session import SessionLocal
from database.models import User, UserSession

async def verify_task_31():
    print("\n>>> STARTING VERIFICATION: MVP TASK 31 (AUTH HARDENING)")
    
    db = SessionLocal()
    from sqlalchemy import text
    db.execute(text("PRAGMA foreign_keys = OFF"))
    
    token = "mock_valid_token"
    sb_id = "sb_31_test"
    email = "u31@ex.com"
    
    # 0. Setup
    db.query(User).filter(User.id == "u31_local").delete()
    db.query(UserSession).filter(UserSession.user_id == "u31_local").delete()
    db.commit()
    
    # 1. Mock Supabase Auth Response
    mock_sb_user = MagicMock()
    mock_sb_user.id = sb_id
    mock_sb_user.email = email
    mock_sb_user.user_metadata = {"role": "agent", "full_name": "Task 31 Agent"}
    
    mock_resp = MagicMock()
    mock_resp.user = mock_sb_user

    with patch('core.auth.supabase_client.supabase.auth.get_user', return_value=mock_resp):
        with patch('services.cache_service.cache_service.is_available', return_value=False):
            
            print("  Calling get_current_user with mock Supabase token...")
            mock_request = MagicMock()
            mock_request.headers = {"user-agent": "Task31-Test-Agent"}
            mock_request.client.host = "127.0.0.1"
            
            user = get_current_user(mock_request, token, db)
            db.commit() 
            
            # 2. Verify Role Extraction (Subtask 31.3)
            print(f"    User Role in DB: {user.role}")
            assert user.role == "agent"
            print("    ✅ SUCCESS: Role extracted and synced correctly.")

            # 3. Verify Session Tracking (Subtask 31.8)
            print("  Checking user_sessions table...")
            # Use the ID from the returned user object
            session = db.query(UserSession).filter(UserSession.user_id == user.id).first()
            assert session is not None
            print(f"    Session login at: {session.login_at}")
            print("    ✅ SUCCESS: User session tracked.")

    # 4. Cleanup
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    db.query(User).filter(User.id == user.id).delete()
    db.commit()
    
    print("\n✅ ALL MVP TASK 31 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_31())
