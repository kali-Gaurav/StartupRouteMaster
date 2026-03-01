
import unittest
from fastapi.testclient import TestClient
import sys
import os
import json
from datetime import datetime

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database import get_db
from services.search_service import SearchService
from database.models import User

# Mock User dependency
from api.dependencies import get_current_user
def override_get_current_user():
    return User(id="test-user", email="test@example.com")

app.dependency_overrides[get_current_user] = override_get_current_user

class TestSearchEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize Cache for testing (use in-memory if possible or same as app)
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="test-cache")
        
        # Initialize DB
        from database import init_db
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init_db())

        cls.client = TestClient(app)

    def test_search_valid(self):
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15",
            "budget": "economy"
        }
        response = self.client.post("/api/search/", json=payload)
        # Should now be 200 or 404 but definitely resolving the codes in logs
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 404:
            self.assertIn("NO_ROUTES_FOUND", response.json()["error"])

    def test_dry_run_resolution(self):
        payload = {
            "source": "NDLS",
            "destination": "MUMBAI",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/?dry_run=true", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["dry_run"])
        self.assertTrue(data["validation"]["source_resolved"])
        self.assertTrue(data["validation"]["destination_resolved"])
        print(f"\nDry Run Result: {data['resolved']}")

    def test_search_same_source_dest(self):
        payload = {
            "source": "NDLS",
            "destination": "NDLS",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Source and destination cannot be the same", response.text)

    def test_search_invalid_characters(self):
        payload = {
            "source": "NDLS!!!",
            "destination": "BCT",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_search_malformed_date(self):
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "not-a-date"
        }
        response = self.client.post("/api/search/", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_autocomplete(self):
        response = self.client.get("/api/search/stations?q=MUM")
        self.assertEqual(response.status_code, 200)
        self.assertIn("stations", response.json())

if __name__ == "__main__":
    unittest.main()
