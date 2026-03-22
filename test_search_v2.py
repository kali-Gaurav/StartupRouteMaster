import asyncio
import logging
from datetime import datetime
import sys
import os

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine import route_engine
from core.route_engine.constraints import RouteConstraints
from database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)

async def test_search():
    print("Initializing database pools...")
    await initialize_database_pools()
    
    # Try NDLS to SBC
    source = "NDLS"
    dest = "SBC"
    date = datetime(2026, 3, 18, 10, 0) # Today 10 AM
    constraints = RouteConstraints()
    
    print(f"Searching for routes from {source} to {dest} on {date}...")
    try:
        routes = await route_engine.search(source, dest, date, constraints)
        print(f"Found {len(routes)} routes.")
        for i, route in enumerate(routes):
            print(f"Route {i+1}: Score={getattr(route, 'score', 'N/A')}, Segments={len(route.segments)}")
            for seg in route.segments:
                print(f"  {seg.departure_code} -> {seg.arrival_code} ({seg.train_number}) {seg.departure_time} - {seg.arrival_time}")
    except Exception as e:
        print(f"Search failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search())
