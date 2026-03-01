import unittest
import asyncio
import os
import sys
from fastapi.testclient import TestClient

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database.session import SessionLocal
from database.models import TrainLiveUpdate, TrainStation, Stop

class TestLiveTrackingBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        
        # Ensure we have a mock station for interpolation
        s1 = cls.db.query(Stop).filter(Stop.code == "NDLS").first()
        if not s1:
            cls.db.add(Stop(id=10001, stop_id="NDLS", code="NDLS", name="New Delhi", latitude=28.6415, longitude=77.2197))
        
        s2 = cls.db.query(Stop).filter(Stop.code == "MTJ").first()
        if not s2:
            cls.db.add(Stop(id=10002, stop_id="MTJ", code="MTJ", name="Mathura Jn", latitude=27.4924, longitude=77.6737))
            
        cls.db.commit()

    def test_tracking_endpoint(self):
        print("\\n[BACKEND] Testing Detailed Status Endpoint")
        train_num = "12002"
        response = self.client.get(f"/api/realtime/train/{train_num}/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        print(f"📊 Live Data Available: {data['metadata']['live_uplink']}")
        print(f"📍 Interpolation Active: {data['metadata']['interpolation_active']}")
        
        self.assertTrue(data["success"])
        self.assertEqual(data["train_number"], train_num)
        
        if data["live_status"]:
            print(f"📢 Live Msg: {data.get('live_status', {}).get('status_message')}")
            print(f"⏱️ Delay: {data.get('live_status', {}).get('delay_minutes')} mins")

if __name__ == "__main__":
    unittest.main()
