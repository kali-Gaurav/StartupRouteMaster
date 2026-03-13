import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from backend.core.route_engine.constraints import RouteConstraints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-4.3")

async def test_orchestrator_surge_logic():
    # 1. Setup Orchestrator with mocked engines
    mock_engine_instance = MagicMock()
    mock_engine_instance._get_current_graph = AsyncMock()
    
    orchestrator = UnifiedRoutingOrchestrator(mock_engine_instance)
    orchestrator.turbo_router = MagicMock()
    orchestrator.ultra_turbo = MagicMock()
    orchestrator.ultra_turbo.find_routes = AsyncMock(return_value=[])
    orchestrator.fast_router = MagicMock()
    orchestrator.raptor = MagicMock()
    
    # Mock internal methods to avoid DB hits
    orchestrator._search_tier_0_hubs = MagicMock(return_value=[])
    orchestrator._global_deduplicate = MagicMock(return_value=[])
    orchestrator._hydrate_fares_and_score = AsyncMock()
    
    # Mock resolve_stations
    mock_source = MagicMock(id=1)
    mock_dest = MagicMock(id=2)
    
    constraints = MagicMock(spec=RouteConstraints)
    constraints.max_transfers = 3
    
    # 2. Test with skip_heavy=True
    logger.info("Testing search_all_tiers with skip_heavy=True...")
    with patch('backend.utils.station_utils.resolve_stations', return_value=(mock_source, mock_dest)):
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.run_in_executor = AsyncMock(return_value=[])
            mock_get_loop.return_value = mock_loop
            
            await orchestrator.search_all_tiers(
                "KOTA", "NDLS", datetime.now(), constraints, skip_heavy=True
            )
            
            # Check what was passed to run_in_executor
            calls = mock_loop.run_in_executor.call_args_list
            from backend.core.route_engine.orchestrator import CPU_BOUND_EXECUTOR
            
            for call in calls:
                executor_used = call[0][0]
                # CPU_BOUND_EXECUTOR should NEVER be used when skip_heavy=True
                assert executor_used != CPU_BOUND_EXECUTOR
            
            logger.info("✅ Verified: Heavy engines were skipped.")

    # 3. Test with skip_heavy=False
    logger.info("Testing search_all_tiers with skip_heavy=False...")
    with patch('backend.utils.station_utils.resolve_stations', return_value=(mock_source, mock_dest)):
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.run_in_executor = AsyncMock(return_value=[])
            mock_get_loop.return_value = mock_loop
            
            await orchestrator.search_all_tiers(
                "KOTA", "NDLS", datetime.now(), constraints, skip_heavy=False
            )
            
            # Should have multiple calls, including some with CPU_BOUND_EXECUTOR
            calls = mock_loop.run_in_executor.call_args_list
            from backend.core.route_engine.orchestrator import CPU_BOUND_EXECUTOR
            cpu_pool_calls = [c for c in calls if c[0][0] == CPU_BOUND_EXECUTOR]
            
            assert len(cpu_pool_calls) >= 2 # FastPath and RAPTOR
            logger.info(f"✅ Verified: Heavy engines called {len(cpu_pool_calls)} times.")

    logger.info("✅ Subtask 4.3: Orchestrator Surge logic Verified.")

if __name__ == "__main__":
    asyncio.run(test_orchestrator_surge_logic())
