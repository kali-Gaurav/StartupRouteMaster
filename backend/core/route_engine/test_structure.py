
import asyncio
import logging
import sys
import os

# Ensure backend is in path
sys.path.append(os.getcwd())

from backend.core.route_engine import RouteEngine, RouteConstraints
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def test_engine():
    print("Initializing RouteEngine...")
    engine = RouteEngine()
    print("RouteEngine initialized successfully.")
    
    # We won't actually run a search as it requires a live DB connection with data, 
    # but we can check if the components are wired up.
    print(f"Raptor instance: {engine.raptor}")
    print(f"Validation Manager: {engine.validation_manager}")
    
    # Check builder
    print(f"Graph Builder: {engine.raptor.graph_builder}")
    
    print("Test passed: RouteEngine structure is valid.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_engine())
