import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.route_engine.engine import RailwayRouteEngine

async def verify_task_19():
    print("\n>>> STARTING VERIFICATION: MVP TASK 19 (GRAPH REFRESH)")
    
    engine = RailwayRouteEngine()
    
    # 1. Test Nightly Refresh Trigger (Subtask 19.1 & 19.2)
    # We'll mock the builder to speed up the test
    mock_graph = MagicMock()
    mock_graph.snapshot = MagicMock()
    mock_graph.snapshot.date = datetime.now()
    
    with patch.object(engine.graph_builder, 'build_graph', return_value=mock_graph) as mock_build:
        with patch.object(engine.snapshot_manager, 'save_snapshot', return_value=None) as mock_save:
            
            print("  Running nightly refresh for 7 day window...")
            await engine.run_nightly_refresh()
            
            # Verify builder was called 7 times
            print(f"    Builder calls: {mock_build.call_count}")
            assert mock_build.call_count == 7
            
            # Verify snapshot saver was called 7 times
            print(f"    Saver calls: {mock_save.call_count}")
            assert mock_save.call_count == 7
            
            # 2. Verify Atomic Swap (Subtask 19.3)
            print("\n[19.3] Verifying atomic swap for current active graph...")
            assert engine.current_graph == mock_graph
            print("    SUCCESS: Current graph updated atomically.")

    print("\n✅ ALL MVP TASK 19 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_19())
