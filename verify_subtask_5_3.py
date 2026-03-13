import asyncio
import logging
from unittest.mock import MagicMock, patch
import os
import sys
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.raptor import OptimizedRAPTOR
from backend.core.route_engine.turbo_router import TurboRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-5.3")

async def test_gc_optimization():
    # 1. Test RAPTOR GC Wrap
    logger.info("Testing RAPTOR GC optimization...")
    raptor = OptimizedRAPTOR()
    mock_graph = MagicMock()
    mock_constraints = MagicMock()
    
    # We patch gc.disable and gc.enable
    with patch('gc.disable') as mock_disable, patch('gc.enable') as mock_enable:
        # Mock dependencies to avoid actual loop
        raptor._deduplicate_routes = MagicMock(return_value=[])
        mock_graph.get_departures_from_stop.return_value = []
        
        raptor._search_single_departure_sync(mock_graph, 1, 2, datetime.now(), mock_constraints)
        
        mock_disable.assert_called_once()
        mock_enable.assert_called_once()
        logger.info("✅ Verified: RAPTOR correctly wraps hot-loop with GC toggle.")

    # 2. Test Turbo GC Wrap
    logger.info("Testing TurboRouter GC optimization...")
    # Mock database to avoid real hits
    with patch('backend.core.route_engine.turbo_router.SessionLocal') as mock_db_cls:
        mock_db = mock_db_cls.return_value
        turbo = TurboRouter()
        
        with patch('gc.disable') as mock_disable, patch('gc.enable') as mock_enable:
            # Mock internal search to avoid SQL
            turbo._get_city_cluster = MagicMock(return_value=[])
            
            turbo.find_routes("KOTA", "NDLS", datetime.now())
            
            mock_disable.assert_called_once()
            mock_enable.assert_called_once()
            logger.info("✅ Verified: TurboRouter correctly wraps hot-loop with GC toggle.")

    logger.info("✅ Subtask 5.3: GC optimization integration Verified.")

if __name__ == "__main__":
    asyncio.run(test_gc_optimization())
