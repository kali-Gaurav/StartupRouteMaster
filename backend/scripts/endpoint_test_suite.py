import unittest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app import app

class TestCoreEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We need to set some env vars maybe
        os.environ["OFFLINE_MODE"] = "true" # Fallback for local tests
        cls.client = TestClient(app)

    def test_ping(self):
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "RouteMaster API")

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("components", data)
        print(f"\nHealth Status: {data['status']}")
        for comp, status in data["components"].items():
            print(f"  - {comp}: {status}")

    def test_health_live(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "live")

    def test_health_ready(self):
        response = self.client.get("/health/ready")
        if response.status_code == 200:
            self.assertEqual(response.json()["status"], "ready")
        else:
            print(f"\nReadiness check returned {response.status_code}: {response.text}")

    def test_metrics(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("python_info", response.text)

    def test_stats(self):
        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_stations", data)
        print(f"\nApp Stats: {data}")

if __name__ == "__main__":
    unittest.main()
