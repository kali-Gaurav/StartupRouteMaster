import unittest
import time
import os
import sys
from fastapi.testclient import TestClient

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database.session import SessionLocal
from database.models import User, Booking

class TestAdminOpsWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Bypass admin token check for simulation
        from api.admin import verify_admin_token
        app.dependency_overrides[verify_admin_token] = lambda: True
        
        cls.client = TestClient(app)
        
        # Ensure test users exist
        db = SessionLocal()
        u = db.query(User).filter(User.id == "manual_guest").first()
        if not u:
            db.add(User(id="manual_guest", email="guest@ops.com", password_hash="dummy"))
            db.commit()
        db.close()

    def test_full_ops_cycle(self):
        print("\\n[OPS STEP 1] User creates a Manual Booking Request")
        payload = {
            "journey_id": "rt_ops_123",
            "travel_date": "2026-05-15",
            "passengers": [
                {"name": "Admin Tester", "age": 30, "gender": "M", "preference": "LB"}
            ],
            "contact_email": "tester@example.com",
            "contact_phone": "1234567890"
        }
        res_req = self.client.post("/api/v2/booking/confirm_manual", json=payload)
        self.assertEqual(res_req.status_code, 200)
        booking_id = res_req.json().get("booking_id")
        print(f"📝 Created Booking ID: {booking_id}")

        print("\\n[OPS STEP 2] Admin views the booking in Admin API")
        res_list = self.client.get("/api/admin/bookings?limit=5", headers={"x-admin-token": "test_ops_token"})
        self.assertEqual(res_list.status_code, 200)
        bookings = res_list.json().get("bookings")
        # Extract ID from object (might be string or dict depending on serialization)
        found = any(str(b.get("id") if isinstance(b, dict) else b.id) == booking_id for b in bookings)
        self.assertTrue(found)
        print(f"📊 Booking found in Admin List: {found}")

        print("\\n[OPS STEP 3] Admin executes the booking (Set PNR + Status)")
        update_url = f"/api/admin/bookings/{booking_id}/manual-update?status=ticket_sent&pnr=OPS12345&notes=ProcessedManual"
        res_update = self.client.post(update_url, headers={"x-admin-token": "test_ops_token"})
        self.assertEqual(res_update.status_code, 200)
        print(f"✅ Admin Update Response: {res_update.json().get('message')}")

        print("\\n[OPS STEP 4] Verify the booking reflects new status")
        db = SessionLocal()
        updated_b = db.query(Booking).filter(Booking.id == booking_id).first()
        self.assertEqual(updated_b.booking_status, "ticket_sent")
        self.assertEqual(updated_b.pnr_number, "OPS12345")
        print(f"🏆 Final DB State: Status={updated_b.booking_status}, PNR={updated_b.pnr_number}")
        db.close()

if __name__ == "__main__":
    unittest.main()
