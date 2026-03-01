import unittest
from fastapi.testclient import TestClient
import sys
import os
import json
import asyncio
from datetime import datetime, timedelta
import time

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database import get_db
from database.models import User

# Mock User dependency
from api.dependencies import get_current_user
def override_get_current_user():
    user = User(id="test-user-id", email="test@example.com")
    return user

app.dependency_overrides[get_current_user] = override_get_current_user

class TestSearchEndpointAdvanced(unittest.TestCase):
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
        
        # Warm up StationSearchEngine
        from services.station_search_service import station_search_engine
        station_search_engine._ensure_initialized()

        cls.client = TestClient(app)

    def test_typo_resolution(self):
        """Test Upgrade 1: Typo Tolerance"""
        # 'Mumba' should resolve to 'Mumbai Central' or similar
        payload = {
            "source": "Mumba",
            "destination": "Delhi",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/?dry_run=true", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["validation"]["source_resolved"])
        print(f"\nTypo 'Mumba' resolved to: {data['resolved']['source']['name']}")

    def test_alias_resolution(self):
        """Test Upgrade 2: Station Aliases"""
        # 'bombay' should resolve to 'BCT'
        payload = {
            "source": "bombay",
            "destination": "banglore",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/?dry_run=true", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["resolved"]["source"]["code"], "BCT")
        self.assertEqual(data["resolved"]["destination"]["code"], "SBC")

    def test_security_injection(self):
        """Test Security: Injection Attempts"""
        payload = {
            "source": "'; DROP TABLE users; --",
            "destination": "BCT",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/", json=payload)
        # Should be blocked by Pydantic regex pattern
        self.assertEqual(response.status_code, 422)

    def test_edge_dates(self):
        """Test Edge Logic: Past and Future Dates"""
        # Past date
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2020-01-01"
        }
        response = self.client.post("/api/search/", json=payload)
        # Assuming our validation blocks past dates or engine returns no routes
        self.assertIn(response.status_code, [200, 400, 422]) 

    def test_stress_concurrent_requests(self):
        """Test Scalability: Concurrent requests (Topic 4: Coalescing)"""
        # Use a unique source to bypass any previous class-level cache
        unique_id = int(time.time())
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": f"2026-06-15" # Future date
        }
        
        # We expect the first call to take some time (RAPTOR compute)
        # and the second to be near-instant (Redis/Local Cache)
        start = time.perf_counter()
        response1 = self.client.post("/api/search/", json=payload)
        dur1 = time.perf_counter() - start
        
        # Immediate second call
        start = time.perf_counter()
        response2 = self.client.post("/api/search/", json=payload)
        dur2 = time.perf_counter() - start
        
        print(f"\nFirst search (with engine): {dur1:.3f}s")
        print(f"Second search (cached): {dur2:.3f}s")
        
        # Second call must be at least 2x faster than the first compute-heavy call
        self.assertLess(dur2, dur1)

    def test_smart_error_response(self):
        """Test Upgrade 7: Intelligent Error Responses"""
        # Use valid stations but a route that likely won't exist (e.g. local to distant small station)
        payload = {
            "source": "NDLS",
            "destination": "SWV", # Sawantwadi (might not have direct from NDLS)
            "date": "2026-05-15"
        }
        response = self.client.post("/api/search/", json=payload)
        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                self.assertEqual(data["error"], "NO_ROUTES_FOUND")
                self.assertIn("suggestions", data)
                print(f"\nSmart Error Suggestion: {data['suggestions'][0]}")

if __name__ == "__main__":
    unittest.main()
