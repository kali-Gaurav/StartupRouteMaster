import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.zonal_loader import lazy_graph_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-5.2")

async def test_lazy_graph_prewarm_direct():
    # 1. Setup mocks for Lazy Loader Class Method
    with patch('backend.core.route_engine.zonal_loader.LazyGraphLoader.get_zone_data', new_callable=AsyncMock) as mock_get_zone:
        
        logger.info("Directly testing prewarm_essential_hubs...")
        
        hub_ids = [101, 202, 303]
        await lazy_graph_loader.prewarm_essential_hubs(hub_ids)
        
        # Verify get_zone_data was called for each hub
        # Each hub_id // 1000 gives 0 in this case
        assert mock_get_zone.call_count == len(hub_ids)
        logger.info(f"✅ Verified: get_zone_data called {mock_get_zone.call_count} times.")
        
        # Verify the zone calculation logic
        from backend.core.route_engine.zonal_loader import LazyGraphLoader
        loader = LazyGraphLoader()
        assert loader.get_zone_id_for_stop(1500) == 1
        assert loader.get_zone_id_for_stop(500) == 0
        logger.info("✅ Zone calculation logic verified.")

    logger.info("✅ Subtask 5.2: Lazy Graph Loader logic Verified.")

if __name__ == "__main__":
    asyncio.run(test_lazy_graph_prewarm_direct())
