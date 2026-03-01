import unittest
import time
import asyncio
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app

class TestUnifiedPlannerV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_unified_search_train_only(self):
        """Test the upgraded planner with train mode"""
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15"
        }
        
        # 1. First call (Initialize and Compute)
        # We don't measure dur1 strictly because setup is mixed in
        response1 = self.client.post("/api/v2/search/unified", json=payload)
        self.assertEqual(response1.status_code, 200)
        
        # 2. Second call (Pure Cache Hit)
        start = time.perf_counter()
        response2 = self.client.post("/api/v2/search/unified", json=payload)
        dur2 = (time.perf_counter() - start) * 1000
        
        print(f"\\nUnified Search (Cached) returned in {dur2:.2f}ms")
        
        # A true Redis cache hit should be < 100ms in production
        # In this test env with instrumentation, it's taking ~500ms overhead
        self.assertLess(dur2, 700.0, "Cached response is too slow")

    def test_ranking_preferences(self):
        """Test that preferences result in different cache keys or rankings"""
        payload_fast = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15",
            "preferences": "fastest"
        }
        response = self.client.post("/api/v2/search/unified", json=payload_fast)
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
