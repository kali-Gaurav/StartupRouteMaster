import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.services.search_service import SearchService
from backend.core.metrics import SurgeLevel
from backend.core.data_structures import Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.4")

async def test_surge_l2_logic():
    mock_db = MagicMock()
    search_svc = SearchService.__new__(SearchService)
    search_svc.db = mock_db
    search_svc.transit_db = mock_db
    search_svc.route_engine = MagicMock()
    search_svc.data_provider = MagicMock()
    
    mock_route = Route() 
    
    # Correct Patching Strategy:
    # 1. Patch where they are USED (backend.services.search_service)
    # 2. Mock the Orchestrator instance returned by the constructor
    # 3. Mock resolve_stations, cache, etc.
    
    with patch('backend.services.search_service.resolve_stations', return_value=(MagicMock(), MagicMock())):
        with patch('backend.services.search_service.multi_layer_cache.initialize', new_callable=AsyncMock):
            with patch('backend.core.route_engine.orchestrator.UnifiedRoutingOrchestrator') as mock_orc_cls:
                mock_orc = mock_orc_cls.return_value
                mock_orc.search_all_tiers = AsyncMock(return_value=[mock_route])
                
                with patch('backend.core.route_engine.categorization.CategorizationEngine.categorize', return_value={}):
                    with patch('backend.services.unlock_service.UnlockService.mask_route', return_value={}):
                        
                        # Case 1: HIGH Surge
                        logger.info("Testing Surge Level: HIGH...")
                        with patch('backend.services.search_service.jit_metrics') as mock_m:
                            mock_m.surge_level = SurgeLevel.HIGH
                            
                            with patch.object(SearchService, '_verify_routes_parallel', new_callable=AsyncMock) as mock_verify:
                                await search_svc.search_routes("KOTA", "NDLS", "2026-03-15")
                                
                                mock_verify.assert_not_called()
                                logger.info("✅ Verified: Verification skipped during HIGH surge.")
                                assert mock_route.metadata.get("verification_skipped") is True

                        # Case 2: NORMAL Surge
                        logger.info("Testing Surge Level: NORMAL...")
                        mock_route.metadata = {}
                        with patch('backend.services.search_service.jit_metrics') as mock_m:
                            mock_m.surge_level = SurgeLevel.NORMAL
                            
                            with patch.object(SearchService, '_verify_routes_parallel', new_callable=AsyncMock, return_value=[mock_route]) as mock_verify:
                                await search_svc.search_routes("KOTA", "NDLS", "2026-03-15")
                                
                                assert mock_verify.call_count >= 1
                                logger.info("✅ Verified: Verification executed during NORMAL surge.")
                                assert mock_route.metadata.get("verification_skipped") is None

    logger.info("✅ Subtask 4.4: Level 2 Surge Protection Verified.")

if __name__ == "__main__":
    asyncio.run(test_surge_l2_logic())
