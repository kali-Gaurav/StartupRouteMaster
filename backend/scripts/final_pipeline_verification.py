import unittest
import time
import json
import os
import sys
from fastapi.testclient import TestClient

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from services.station_search_service import station_search_engine
from core.route_engine import route_engine

class FinalPipelineVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "="*50)
        print("🚀 STARTING FINAL PIPELINE VERIFICATION")
        print("="*50)
        
        # 1. Warm up Station Engine (RAM Index)
        start = time.perf_counter()
        station_search_engine._ensure_initialized()
        print(f"✅ Station Engine Ready: {len(station_search_engine._stations)} stations in {(time.perf_counter()-start)*1000:.2f}ms")
        
        cls.client = TestClient(app)

    def test_01_autocomplete_pipeline(self):
        print("\n[STEP 1] Testing Autocomplete Pipeline (Frontend -> Backend -> RAM Trie)")
        query = "bombay"
        response = self.client.get(f"/api/stations/suggest?q={query}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify Alias resolution (bombay -> BCT)
        codes = [s["code"] for s in data]
        print(f"🔍 Query '{query}' resolved to codes: {codes}")
        self.assertIn("BCT", codes)
        self.assertLess(response.elapsed.total_seconds(), 0.1, "Latency too high for autocomplete")

    def test_02_chat_intent_pipeline(self):
        print("\n[STEP 2] Testing Chat Intent Pipeline (Frontend -> Backend -> AI Resolution)")
        payload = {
            "message": "book ticket from delhi to mumbai",
            "session_id": "final_verify_session"
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        print(f"🤖 Chat Reply: {data['reply']}")
        print(f"🎯 Detected Intent: {data['intent']}")
        print(f"📍 Collected Stations: {data['collected']}")
        
        self.assertEqual(data["intent"], "search")
        self.assertEqual(data["collected"]["source_code"], "NDLS")
        self.assertEqual(data["collected"]["destination_code"], "BCT")

    def test_03_full_search_pipeline(self):
        print("\n[STEP 3] Testing Full Search Pipeline (Frontend -> Backend -> RAPTOR -> Cache)")
        # Using codes resolved in Step 2
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15",
            "budget": "standard"
        }
        
        # First call (Compute)
        print("⏳ Executing Route Search (First Run - Compute)...")
        start = time.perf_counter()
        response1 = self.client.post("/api/search/", json=payload)
        dur1 = time.perf_counter() - start
        
        self.assertIn(response1.status_code, [200, 404]) # 404 is valid if no trains on that day, but not 500
        print(f"⏱️  Compute Run: {dur1:.2f}s")
        
        # Second call (Redis Cache)
        print("⚡ Executing Route Search (Second Run - Cache)...")
        start = time.perf_counter()
        response2 = self.client.post("/api/search/", json=payload)
        dur2 = time.perf_counter() - start
        print(f"⏱️  Cache Run: {dur2:.2f}s")
        
        self.assertEqual(response2.status_code, response1.status_code)
        if dur1 > 0.5: # Only compare if first run was actually heavy
            self.assertLess(dur2, dur1, "Cache did not improve performance")

    def test_04_database_integrity(self):
        print("\n[STEP 4] Verifying Database Integrity (Supabase + SQLite)")
        from database.session import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            # Check Supabase connectivity
            res = db.execute(text("SELECT 1")).fetchone()
            print("✅ Supabase (Postgres) Connectivity: OK")
            
            # Check TransitGraph.db Stop Count
            import sqlite3
            conn = sqlite3.connect('backend/database/transit_graph.db')
            count = conn.execute("SELECT count(*) FROM stops").fetchone()[0]
            print(f"✅ TransitGraph.db (SQLite) Integrity: {count} stops found")
            conn.close()
            self.assertGreater(count, 5000)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
