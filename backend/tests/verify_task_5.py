import sys
import time
from unittest.mock import MagicMock

# Mock heavy/problematic modules
sys.modules['pandas'] = MagicMock()
sys.modules['services.ml.reliability_model'] = MagicMock()
sys.modules['core.routing.frequency_aware_range'] = MagicMock()
sys.modules['core.route_engine.raptor'] = MagicMock()
sys.modules['core.route_engine.engine'] = MagicMock()

import unittest
from unittest.mock import patch
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from sqlalchemy import text

class TestTurboRouterClusters(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.patcher = patch('core.route_engine.turbo_router.SessionLocal', return_value=self.mock_db)
        self.patcher.start()
        self.router = TurboRouter()

    def tearDown(self):
        self.patcher.stop()

    def test_transfer_penalty_logic(self):
        # Case 1: Same station
        self.assertEqual(self.router._get_transfer_penalty(self.mock_db, "NDLS", "NDLS"), 0)
        
        # Case 2: Different stations with distance in matrix
        # Mock DB response for hub_distance_matrix
        self.mock_db.execute.return_value.fetchone.return_value = (5.0,) # 5 km
        # Penalty = 10 + 5*5 = 35
        penalty = self.router._get_transfer_penalty(self.mock_db, "NDLS", "NZM")
        self.assertEqual(penalty, 35)
        
        # Case 3: No entry in matrix
        self.mock_db.execute.return_value.fetchone.return_value = None
        self.assertEqual(self.router._get_transfer_penalty(self.mock_db, "NDLS", "XYZ"), 60)

    def test_cluster_resolution_latency(self):
        # Benchmark _get_city_cluster
        self.mock_db.execute.return_value.fetchall.return_value = [(1,), (2,), (3,)]
        
        start = time.time()
        iterations = 1000
        for _ in range(iterations):
            self.router._get_city_cluster(self.mock_db, "NDLS")
        end = time.time()
        
        avg_ms = ((end - start) * 1000) / iterations
        print(f"\\nCluster Resolution Avg Latency: {avg_ms:.4f} ms")
        self.assertTrue(avg_ms < 2.0) # Should be incredibly fast with DB hit mocked/indexed

    def test_transfer_penalty_latency(self):
        # Benchmark _get_transfer_penalty
        self.mock_db.execute.return_value.fetchone.return_value = (5.0,)
        
        start = time.time()
        iterations = 1000
        for _ in range(iterations):
            self.router._get_transfer_penalty(self.mock_db, "NDLS", "NZM")
        end = time.time()
        
        avg_ms = ((end - start) * 1000) / iterations
        print(f"\\nTransfer Penalty Avg Latency: {avg_ms:.4f} ms")
        self.assertTrue(avg_ms < 2.0)

if __name__ == "__main__":
    unittest.main()
