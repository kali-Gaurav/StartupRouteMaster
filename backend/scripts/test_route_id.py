import os
import sys
import unittest
import json
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app
from database.session import SessionLocal, init_db
from database.models import User, PrecalculatedRoute
from core.redis import redis_client
from api.dependencies import get_current_user

# Mock User dependency
def override_get_current_user():
    user = User(id="test-user-id", email="test@test.com")
    return user

app.dependency_overrides[get_current_user] = override_get_current_user

class TestRouteIdEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["OFFLINE_MODE"] = "true"
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        
        # Insert a fake PrecalculatedRoute for legacy fallback test
        cls.legacy_id = str(uuid.uuid4())
        route = PrecalculatedRoute(
            id=cls.legacy_id,
            source="Mumbai",
            destination="Delhi",
            total_duration="15h",
            total_cost=1500.0,
            segments=[]
        )
        cls.db.add(route)
        cls.db.commit()

        # Insert a fake Journey into Redis cache for modern route test
        cls.modern_id = f"rt_12345_{int(datetime.utcnow().timestamp())}"
        journey_data = {
            "source": "Chennai",
            "destination": "Bangalore",
            "segments": [{
                "mode": "train",
                "from": "Chennai",
                "to": "Bangalore",
                "duration": "6h",
                "cost": 800.0,
                "details": "Shatabdi Exp"
            }],
            "total_duration": "6h",
            "total_fare": 800.0,
            "timestamp": datetime.utcnow().isoformat()
        }
        redis_client.set(f"journey:{cls.modern_id}", json.dumps(journey_data))

    @classmethod
    def tearDownClass(cls):
        cls.db.query(PrecalculatedRoute).filter(PrecalculatedRoute.id == cls.legacy_id).delete()
        cls.db.commit()
        cls.db.close()
        redis_client.delete(f"journey:{cls.modern_id}")

    def test_get_legacy_route(self):
        response = self.client.get(f"/api/routes/{self.legacy_id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["source"], "Mumbai")
        self.assertEqual(data["destination"], "Delhi")

    def test_get_modern_route_from_cache(self):
        response = self.client.get(f"/api/routes/{self.modern_id}")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["source"], "Chennai")
        self.assertEqual(data["destination"], "Bangalore")

    def test_get_route_not_found(self):
        response = self.client.get(f"/api/routes/{str(uuid.uuid4())}")
        self.assertEqual(response.status_code, 404)

    def test_get_route_invalid_format(self):
        # Even with string it tries to query UUID for UnlockedRoute, so test bad format if UUID expected
        response = self.client.get("/api/routes/invalid-format-string")
        # Could be 400 or 404 depending on how the DB handles it
        self.assertIn(response.status_code, [400, 404])

if __name__ == "__main__":
    unittest.main()
