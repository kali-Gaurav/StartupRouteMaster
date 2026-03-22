
import asyncio
from datetime import datetime
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.engine import route_engine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona
from database.session import SessionTransit

async def analyze_sbc_mas():
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=100)
    
    graph = await route_engine._get_current_graph(departure_date)
    
    from utils.station_utils import resolve_stations
    src_stop, dst_stop = resolve_stations(db, "SBC", "MAS")
    
    print(f"SBC ID: {src_stop.id}, MAS ID: {dst_stop.id}")
    
    # Check all trips that stop at both
    from sqlalchemy import text
    query = text("""
        SELECT st1.trip_id, st1.departure_timestamp, st2.arrival_timestamp
        FROM stop_times st1
        JOIN stop_times st2 ON st1.trip_id = st2.trip_id
        WHERE st1.stop_id = :src AND st2.stop_id = :dst
        AND st1.stop_sequence < st2.stop_sequence
        AND st1.departure_timestamp >= :ts
        LIMIT 10
    """)
    res = db.execute(query, {"src": src_stop.id, "dst": dst_stop.id, "ts": int(departure_date.timestamp())}).fetchall()
    print(f"Trips stopping at both in DB: {len(res)}")
    for row in res:
        print(f"  Trip {row[0]}: Dep {datetime.fromtimestamp(row[1])}, Arr {datetime.fromtimestamp(row[2])}")
        
        # Check if these trips are in our graph
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        t_info = t_index.get(row[0])
        print(f"    In graph index: {t_info is not None}")
        
        if t_info:
            t_start, t_count = t_info
            trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
            found_src = False
            found_dst = False
            for i in range(t_count):
                node = trip_nodes[t_start + i]
                if node['stop_id'] == src_stop.id: found_src = True
                if node['stop_id'] == dst_stop.id: found_dst = True
            print(f"    Found src in graph trip: {found_src}")
            print(f"    Found dst in graph trip: {found_dst}")

    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(analyze_sbc_mas())
