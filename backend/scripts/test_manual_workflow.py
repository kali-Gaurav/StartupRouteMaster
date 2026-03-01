import unittest
import json
import os
import sys
import time
from fastapi.testclient import TestClient

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app

class TestManualBookingWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from database.session import SessionLocal
        from database.models import User
        db = SessionLocal()
        try:
            # Create test users to prevent foreign key violations
            test_user = db.query(User).filter(User.id == "test-user-id").first()
            if not test_user:
                db.add(User(id="test-user-id", email="test@test.com", password_hash="dummy"))
                
            manual_guest = db.query(User).filter(User.id == "manual_guest").first()
            if not manual_guest:
                db.add(User(id="manual_guest", email="guest@test.com", password_hash="dummy"))
            db.commit()
        finally:
            db.close()
        
        cls.client = TestClient(app)

    def test_01_seat_priority_search(self):
        print("\\n[STEP 1] Testing Seat-Priority Search")
        payload = {
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-05-15"
        }
        response = self.client.post("/api/v2/search/unified", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"🔍 Found {len(data)} journeys.")
        if len(data) > 0:
            print(f"🏆 Top Journey Seat Status: {data[0].get('availability_status')}")
            self.assertIn(data[0].get('availability_status'), ["AVAILABLE", "CHECKING"])

    def test_02_upi_payment_order(self):
        print("\\n[STEP 2] Testing UPI Payment Order Creation")
        payload = {
            "route_id": "rt_test_123",
            "travel_date": "2026-05-15",
            "is_unlock_payment": True
        }
        from api.dependencies import get_current_user
        from database.models import User
        app.dependency_overrides[get_current_user] = lambda: User(id="test-user-id", email="test@test.com")
        
        response = self.client.post("/api/payments/create_order_v2", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"🔗 UPI Link Generated: {data.get('upi_link')}")
        self.assertEqual(data.get("payment_mode"), "upi_intent")
        self.assertIn("upi://pay", data.get("upi_link", ""))

    def test_03_manual_confirm_and_unlock(self):
        print("\\n[STEP 3] Testing Manual Payment Confirmation")
        res_create = self.client.post("/api/payments/create_order_v2", json={
            "route_id": "rt_unlock_test", "travel_date": "2026-05-15", "is_unlock_payment": True
        })
        p_id = res_create.json().get("payment_id")
        
        response = self.client.post(f"/api/payments/manual_confirm_payment?payment_id={p_id}")
        self.assertEqual(response.status_code, 200)
        print(f"✅ Unlock Status: {response.json().get('message')}")
        self.assertTrue("unlocked" in response.json().get('message').lower())

    def test_04_manual_booking_details(self):
        print("\\n[STEP 4] Testing Manual Booking Details Capture")
        payload = {
            "journey_id": "rt_manual_123",
            "travel_date": "2026-05-15",
            "passengers": [
                {"name": "Gaurav Nagar", "age": 25, "gender": "M", "preference": "LB"}
            ],
            "contact_email": "gaurav@example.com",
            "contact_phone": "9876543210"
        }
        response = self.client.post("/api/v2/booking/confirm_manual", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"📝 Booking Message: {data.get('message')}")
        self.assertTrue(data.get("success"))
        self.assertIn("manually book", data.get("message"))

if __name__ == "__main__":
    unittest.main()
