import sys
import os
import asyncio
from datetime import datetime

# Add backend to path
sys.path.append("backend")

from core.route_engine.engine import RailwayRouteEngine

async def test_init():
    print(">>> Initializing RailwayRouteEngine...")
    engine = RailwayRouteEngine()
    print(">>> Initialization complete.")

if __name__ == "__main__":
    asyncio.run(test_init())
