import asyncio
import logging
from datetime import datetime
from core.route_engine.engine import RailwayRouteEngine as RouteEngine

logging.basicConfig(level=logging.INFO)

from database.session import initialize_database_pools

async def build_snapshot():
    await initialize_database_pools()
    engine = RouteEngine()
    target_date = datetime(2026, 3, 20)
    print(f"Building snapshot for {target_date.date()}...")
    new_graph = await engine.graph_builder.build_graph(target_date)
    await engine.snapshot_manager.save_snapshot(new_graph.snapshot)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(build_snapshot())
