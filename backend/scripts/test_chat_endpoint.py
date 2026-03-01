import unittest
import asyncio
from fastapi.testclient import TestClient
import sys
import os
import time
from unittest.mock import patch, MagicMock

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database import get_db
from database.models import User

# Mock User dependency
from api.dependencies import get_current_user, get_optional_user
def override_get_current_user():
    return User(id="test-user-id", email="test@example.com")

def override_get_optional_user():
    return User(id="test-user-id", email="test@example.com")

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_optional_user] = override_get_optional_user

class TestChatEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize Cache for testing
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="test-cache")
        
        # Initialize DB
        from database import init_db
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init_db())
        
        cls.client = TestClient(app)

    def test_intent_search(self):
        """Test Upgrade 1: Deterministic Intent First (Search)"""
        payload = {
            "message": "train from delhi to mumbai",
            "session_id": "test_session_1"
        }
        start = time.perf_counter()
        response = self.client.post("/api/chat", json=payload)
        dur = time.perf_counter() - start
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "search")
        self.assertTrue(data["trigger_search"])
        print(f"\\nSearch Intent took: {dur:.3f}s")
        # Should be fast since it doesn't use LLM
        self.assertLess(dur, 2.0)

    def test_intent_sos(self):
        """Test Upgrade 4: Safety Intelligence Layer"""
        payload = {
            "message": "I am unsafe help me",
            "session_id": "test_session_2"
        }
        start = time.perf_counter()
        response = self.client.post("/api/chat", json=payload)
        dur = time.perf_counter() - start
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "trigger_sos")
        self.assertEqual(data["state"], "idle") # or sos
        print(f"\\nSOS Intent took: {dur:.3f}s")
        self.assertLess(dur, 0.5) # MUST be extremely fast

    def test_edge_cases(self):
        """Test Edge Cases"""
        payload = {
            "message": "???",
            "session_id": "test_session_3"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        
        payload_long = {
            "message": "A" * 1000,
            "session_id": "test_session_3"
        }
        response = self.client.post("/api/chat", json=payload_long)
        self.assertIn(response.status_code, [200, 422, 400])

if __name__ == "__main__":
    unittest.main()
