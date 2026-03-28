
import asyncio
from datetime import datetime
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.route_engine.builder import GraphBuilder
from database.session import initialize_database_pools

async def rebuild_for_nexus():
    await initialize_database_pools()
    from core.route_engine.snapshot_manager import SnapshotManager
    manager = SnapshotManager()
    with ThreadPoolExecutor(max_workers=1) as executor:
        builder = GraphBuilder(executor=executor)
        graph = await builder.build_graph(datetime(2026, 3, 30))
        # [Task 121: Elite Yield] Always build TBR Edge connectivity during Rebuild
        from core.route_engine.tbr_edge_builder import TBREdgeBuilder
        edge_count = TBREdgeBuilder().build_tbr_edges(graph.snapshot)
        
        print(f"✅ Rebuild complete and SAVED. Snapshot v{graph.snapshot.version} created.")
        print(f"🚄 TBR Edges: {edge_count} compiled and saved.")

if __name__ == "__main__":
    asyncio.run(rebuild_for_nexus())
