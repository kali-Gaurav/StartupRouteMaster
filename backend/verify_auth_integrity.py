import sys
import os
import uuid
import unittest
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.session import SessionLocal, initialize_database_pools
from database.models import User, Profile
from api.dependencies import get_current_user

class MockRequest:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client = MagicMock()
        self.client.host = host
        self.headers = headers or {}

class TestAuthIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set environment to development for local sqlite
        os.environ["ENVIRONMENT"] = "development"
        # Initialize database pools
        asyncio.run(initialize_database_pools())

    def setUp(self):
        self.db = SessionLocal()
        # Clean up any test users
        self.db.query(User).filter(User.email.like("test-%")).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def create_mock_supabase_user(self, id, email=None, phone=None, metadata=None):
        mock_user = MagicMock()
        # Crucial fix: return actual strings for ID/email/phone, not another mock
        type(mock_user).id = PropertyMock(return_value=id)
        type(mock_user).email = PropertyMock(return_value=email)
        type(mock_user).phone = PropertyMock(return_value=phone)
        type(mock_user).user_metadata = PropertyMock(return_value=metadata or {})
        return mock_user

    @patch("api.dependencies.supabase")
    def test_email_user_sync(self, mock_supabase):
        """Test that a new Supabase email user is correctly synced to local DB."""
        sb_id = str(uuid.uuid4())
        test_email = f"test-{uuid.uuid4()}@example.com"
        
        mock_user = self.create_mock_supabase_user(sb_id, email=test_email, metadata={"full_name": "Test User", "role": "user"})
        # Supabase client returns a response object with a .user property
        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_supabase.auth.get_user.return_value = mock_resp

        request = MockRequest()
        user = get_current_user(request, token="mock-token", db=self.db)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.email, test_email)
        self.assertEqual(user.supabase_id, sb_id)
        
        profile = self.db.query(Profile).filter(Profile.id == sb_id).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Test User")

    @patch("api.dependencies.supabase")
    def test_phone_user_sync(self, mock_supabase):
        """Test that a new Supabase phone user is correctly synced to local DB."""
        sb_id = str(uuid.uuid4())
        test_phone = "+919876543210"
        
        mock_user = self.create_mock_supabase_user(sb_id, phone=test_phone, metadata={"full_name": "Phone User", "role": "user"})
        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_supabase.auth.get_user.return_value = mock_resp

        request = MockRequest()
        user = get_current_user(request, token="mock-token", db=self.db)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.supabase_id, sb_id)
        
        profile = self.db.query(Profile).filter(Profile.id == sb_id).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Phone User")

    @patch("api.dependencies.supabase")
    def test_admin_role_sync(self, mock_supabase):
        """Test that roles from Supabase metadata are reflected locally."""
        sb_id = str(uuid.uuid4())
        test_email = f"test-admin-{uuid.uuid4()}@example.com"
        
        mock_user = self.create_mock_supabase_user(sb_id, email=test_email, metadata={"full_name": "Admin User", "role": "admin"})
        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_supabase.auth.get_user.return_value = mock_resp

        request = MockRequest()
        
        user = get_current_user(request, token="token1", db=self.db)
        self.assertEqual(user.role, "admin")

        # Change role to 'user'
        mock_user.user_metadata["role"] = "user"
        user = get_current_user(request, token="token2", db=self.db)
        self.assertEqual(user.role, "user")

    @patch("api.dependencies.supabase")
    def test_existing_user_linking(self, mock_supabase):
        """Test that an existing local user (pre-supabase) is linked correctly."""
        test_email = f"test-legacy-{uuid.uuid4()}@example.com"
        legacy_user = User(id=str(uuid.uuid4()), email=test_email, role="user")
        self.db.add(legacy_user)
        self.db.commit()

        sb_id = str(uuid.uuid4())
        mock_user = self.create_mock_supabase_user(sb_id, email=test_email, metadata={"full_name": "Legacy User"})
        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_supabase.auth.get_user.return_value = mock_resp

        request = MockRequest()
        user = get_current_user(request, token="mock-token", db=self.db)

        self.assertEqual(user.id, legacy_user.id)
        self.assertEqual(user.supabase_id, sb_id)

if __name__ == "__main__":
    # Ensure logs don't clutter test output
    import logging
    logging.getLogger("database-session").setLevel(logging.ERROR)
    unittest.main()
