import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Ensure backend in path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.auth import AuthManager
from database.session import get_db
from database.models import User, Profile, UserSession

def test_auth_manager_sync():
    print("Testing AuthManager Sync Logic...")
    mock_db = MagicMock()
    auth_manager = AuthManager(mock_db)
    
    # Mock UserService
    auth_manager.user_service = MagicMock()
    auth_manager.user_service.get_user_by_supabase_id.return_value = None
    auth_manager.user_service.get_user_by_email.return_value = None
    
    # Mock User object to be returned
    new_user = User(id="local-uuid", email="test@example.com", supabase_id="sb-uuid", is_verified=False)
    auth_manager.user_service.create_user_with_data.return_value = new_user
    
    # Mock Supabase user object
    sb_user = MagicMock()
    sb_user.id = "sb-uuid"
    sb_user.email = "test@example.com"
    sb_user.user_metadata = {"full_name": "Test User", "role": "user"}
    
    # Run sync
    user = auth_manager.sync_user(sb_user)
    
    print(f"Sync successful: User {user.email} with ID {user.id}")
    assert user.email == "test@example.com"
    assert user.supabase_id == "sb-uuid"
    
    # Verify create_user_with_data was called with correct metadata
    auth_manager.user_service.create_user_with_data.assert_called_once()
    call_args = auth_manager.user_service.create_user_with_data.call_args[0][0]
    assert call_args["full_name"] == "Test User"
    print("✅ User synchronization logic verified.")

def test_session_tracking():
    print("Testing Session Tracking Logic...")
    mock_db = MagicMock()
    auth_manager = AuthManager(mock_db)
    
    user = User(id="user-1", last_active_at=datetime.utcnow() - timedelta(minutes=10))
    mock_request = MagicMock()
    mock_request.headers = {"user-agent": "Mozilla/5.0", "x-forwarded-for": "1.2.3.4"}
    mock_request.client.host = "1.2.3.4"
    
    auth_manager.track_session(user, mock_request)
    
    # Check if add/commit was called for UserSession
    assert mock_db.add.called
    assert mock_db.commit.called
    print("✅ Session tracking logic verified.")

if __name__ == "__main__":
    try:
        test_auth_manager_sync()
        test_session_tracking()
        print("\n🎉 Backend Authentication Logic is VALIDATED.")
    except Exception as e:
        print(f"\n❌ Validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
