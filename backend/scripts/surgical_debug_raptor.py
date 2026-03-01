import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from core.route_engine import route_engine
from core.route_engine.constraints import RouteConstraints

async def debug_raptor():
    print("🚀 Initializing Route Engine...")
    await route_engine.initialize()
    
    # NDLS ID: 111
    # MTJ ID: 110
    source_id = 111
    dest_id = 110
    date = datetime(2026, 5, 15, 10, 0)
    
    constraints = RouteConstraints(max_transfers=0, range_minutes=1440)
    
    graph = await route_engine._get_current_graph(date)
    print(f"Graph loaded: {len(graph.stop_cache)} stops")
    
    # Manual Round 0 check
    departures = graph.get_departures_from_stop(source_id, date)
    print(f"Departures from NDLS (111): {len(departures)}")
    
    for dep_time, trip_id in departures[:5]:
        segments = graph.get_trip_segments(trip_id)
        print(f"Trip {trip_id} has {len(segments)} segments")
        # Check if source and destination are in this trip
        trip_stop_ids = [s.departure_stop_id for s in segments] + [segments[-1].arrival_stop_id]
        print(f"  - Stops: {trip_stop_ids}")
        if source_id in trip_stop_ids and dest_id in trip_stop_ids:
            print("  ✅ Trip contains both source and destination!")

    print("\n🚀 Running RAPTOR search...")
    routes = await route_engine.raptor.find_routes(source_id, dest_id, date, constraints, graph=graph)
    print(f"RAPTOR Result: {len(routes)} routes found.")

if __name__ == "__main__":
    asyncio.run(debug_raptor())
