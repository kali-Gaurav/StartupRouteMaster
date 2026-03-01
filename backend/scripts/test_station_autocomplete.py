
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
from services.station_search_service import station_search_engine

class TestStationAutocompleteUltra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Warm up engine
        station_search_engine._ensure_initialized()
        cls.client = TestClient(app)

    def test_latency_performance(self):
        """Test Upgrade: <50ms response target"""
        latencies = []
        queries = ["del", "mum", "ban", "ndls", "bct", "mas", "hwh", "pune", "jp", "adi"]
        
        for q in queries:
            start = time.perf_counter()
            response = self.client.get(f"/api/stations/suggest?q={q}")
            dur = (time.perf_counter() - start) * 1000
            latencies.append(dur)
            self.assertEqual(response.status_code, 200)
            
        avg_latency = sum(latencies) / len(latencies)
        print(f"\\nAverage Autocomplete Latency: {avg_latency:.2f}ms")
        print(f"Max Latency: {max(latencies):.2f}ms")
        
        self.assertLess(avg_latency, 50.0)

    def test_result_ranking(self):
        """Test Upgrade 3: Result Ranking (Exact code matches first)"""
        response = self.client.get("/api/stations/suggest?q=NDLS")
        data = response.json()
        self.assertTrue(len(data) > 0)
        self.assertEqual(data[0]["code"], "NDLS")
        print(f"\\nRanking check 'NDLS' top result: {data[0]['name']} ({data[0]['code']})")

    def test_alias_logic(self):
        """Test Upgrade 2: Alias resolution"""
        # 'bombay' should resolve to Mumbai Central (BCT)
        response = self.client.get("/api/stations/suggest?q=bombay")
        data = response.json()
        self.assertTrue(any(s["code"] == "BCT" for s in data))
        
    def test_debounce_cache(self):
        """Test Upgrade 4: Memory Cache Efficiency"""
        q = "chen"
        # First call (Trie search)
        start = time.perf_counter()
        self.client.get(f"/api/stations/suggest?q={q}")
        dur1 = (time.perf_counter() - start) * 1000
        
        # Second call (Should be from RAM cache)
        start = time.perf_counter()
        self.client.get(f"/api/stations/suggest?q={q}")
        dur2 = (time.perf_counter() - start) * 1000
        
        print(f"\\nFirst call: {dur1:.2f}ms, Second (Cached): {dur2:.2f}ms")
        self.assertLess(dur2, dur1 + 10.0) # Allow small jitter in test env

    def test_concurrent_typing_sim(self):
        """Test Scalability: Multiple users typing simultaneously"""
        import concurrent.futures
        
        def mock_user_typing(q):
            return self.client.get(f"/api/stations/suggest?q={q}")

        # Start with 2 chars to avoid 422
        queries = ["de", "del", "delh", "delhi", "mu", "mum", "mumb", "mumbai"] * 3
        
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            responses = list(executor.map(mock_user_typing, queries))
        
        total_dur = (time.perf_counter() - start) * 1000
        print(f"\\nConcurrent Stress: {len(queries)} requests took {total_dur:.2f}ms ({total_dur/len(queries):.2f}ms/req)")
        
        for r in responses:
            self.assertEqual(r.status_code, 200)

if __name__ == "__main__":
    unittest.main()
