
import asyncio
from datetime import datetime
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# [Task 117.9] Path mapping for dynamic script invocation
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.append(_root)


from core.route_engine.builder import GraphBuilder
from database.session import initialize_database_pools

async def rebuild_for_nexus():
    await initialize_database_pools()
    from core.route_engine.snapshot_manager import SnapshotManager
    manager = SnapshotManager()
    with ThreadPoolExecutor(max_workers=1) as executor:
        builder = GraphBuilder(executor=executor)
        graph = await builder.build_graph(datetime(2026, 3, 30))
        if graph is None:
            raise RuntimeError("Nexus rebuild failed: build_graph returned None")

        snapshot = graph.snapshot
        if snapshot is None:
            raise RuntimeError("Nexus rebuild failed: graph snapshot is missing")

        # [Task 121: Elite Yield] Always build TBR Edge connectivity during Rebuild
        from core.route_engine.tbr_edge_builder import TBREdgeBuilder
        edge_count = TBREdgeBuilder().build_tbr_edges(snapshot)
        
        print(f"✅ Rebuild complete and SAVED. Snapshot v{snapshot.version} created.")
        print(f"🚄 TBR Edges: {edge_count} compiled and saved.")

if __name__ == "__main__":
    asyncio.run(rebuild_for_nexus())
