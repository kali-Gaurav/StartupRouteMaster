import asyncio
import logging
from datetime import datetime
from backend.core.route_engine import route_engine
from backend.core.route_engine.constraints import RouteConstraints
from backend.database.session import initialize_database_pools

logging.basicConfig(level=logging.INFO)

async def test_search():
    await initialize_database_pools()
    
    # Try NDLS to SBC
    source = "NDLS"
    dest = "SBC"
    date = datetime(2026, 3, 18, 10, 0) # Today 10 AM
    constraints = RouteConstraints()
    
    print(f"Searching for routes from {source} to {dest} on {date}...")
    routes = await route_engine.search(source, dest, date, constraints)
    
    print(f"Found {len(routes)} routes.")
    for i, route in enumerate(routes):
        print(f"Route {i+1}: Score={route.score}, Segments={len(route.segments)}")
        for seg in route.segments:
            print(f"  {seg.departure_code} -> {seg.arrival_code} ({seg.train_number}) {seg.departure_time} - {seg.arrival_time}")

if __name__ == "__main__":
    asyncio.run(test_search())
