import sys
from unittest.mock import MagicMock

# Mock heavy/problematic modules before importing TurboRouter
sys.modules['pandas'] = MagicMock()
sys.modules['services.ml.reliability_model'] = MagicMock()
sys.modules['core.routing.frequency_aware_range'] = MagicMock()
sys.modules['core.route_engine.raptor'] = MagicMock()
sys.modules['core.route_engine.engine'] = MagicMock()

import unittest
from unittest.mock import patch
from datetime import datetime
from core.route_engine.turbo_router import TurboRouter
from core.engines.frontier import FrontierRoute

class TestTurboRouterFrontier(unittest.TestCase):
    def setUp(self):
        # Mock SessionLocal and db
        self.mock_db = MagicMock()
        self.patcher = patch('core.route_engine.turbo_router.SessionLocal', return_value=self.mock_db)
        self.patcher.start()
        
        # Initialize TurboRouter
        self.router = TurboRouter()

    def tearDown(self):
        self.patcher.stop()

    def test_frontier_manager_initialization(self):
        self.assertIsNotNone(self.router.frontier_manager)
        self.assertEqual(self.router.frontier_manager.max_routes, 10)

    def test_time_to_min(self):
        self.assertEqual(self.router._time_to_min("10:30:00"), 630)
        self.assertEqual(self.router._time_to_min("00:00:00"), 0)
        self.assertEqual(self.router._time_to_min("23:59:00"), 1439)

    @patch('core.route_engine.turbo_router.TurboRouter._search_direct_binary')
    @patch('core.route_engine.turbo_router.TurboRouter._get_city_cluster')
    @patch('core.route_engine.turbo_router.TurboRouter._get_station_code')
    def test_frontier_pruning_in_find_routes(self, mock_get_code, mock_cluster, mock_direct):
        # Mock setup
        # Source ID 1 -> NDLS, Destination ID 2 -> HWH
        mock_cluster.side_effect = [[1], [2]] # src_ids, dst_ids
        mock_get_code.side_effect = ["NDLS", "HWH"]
        
        # Direct route found from NDLS to HWH
        mock_direct.return_value = [{
            "train_no": "12345",
            "dep": "10:00:00",
            "arr": "12:00:00",
            "distance": 100.0
        }]
        
        # Search routes
        self.router.find_routes("NDLS", "HWH", datetime(2025, 3, 10))
        
        # Check if frontier was populated for destination HWH
        hwh_frontier = self.router.frontier_manager.get_frontier(hash("HWH"))
        self.assertEqual(len(hwh_frontier.routes), 1)
        self.assertEqual(hwh_frontier.routes[0].arrival_time, 720) # 12:00
        self.assertEqual(hwh_frontier.routes[0].transfers, 0)
        print("Frontier Pruning Test: OK")

if __name__ == "__main__":
    unittest.main()
