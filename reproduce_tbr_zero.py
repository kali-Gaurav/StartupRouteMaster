
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

async def debug_tbr():
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=100)
    
    graph = await route_engine._get_current_graph(departure_date)
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    tbr = orchestrator.tbr_router
    
    # Debug BPL -> RKMP (Bhopal -> Rani Kamalapati)
    from utils.station_utils import resolve_stations
    src_code, dst_code = "BPL", "RKMP"
    src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
    
    print(f"Source: {src_stop.name} (ID: {src_stop.id})")
    print(f"Dest: {dst_stop.name} (ID: {dst_stop.id})")
    
    from utils.station_utils import get_metro_group_codes
    src_ids = {src_stop.id}
    for code in get_metro_group_codes(src_stop.code):
        s = graph.get_stop_by_code(code)
        if s: src_ids.add(s.id)
    
    dst_ids = {dst_stop.id}
    for code in get_metro_group_codes(dst_stop.code):
        d = graph.get_stop_by_code(code)
        if d: dst_ids.add(d.id)
        
    print(f"src_ids: {src_ids}")
    print(f"dst_ids: {dst_ids}")
    
    deps = graph.get_departures_from_stop(src_stop.id, departure_date, 1440)
    print(f"Found {len(deps)} departures from BPL after {departure_date}")
    
    if deps:
        dt, tid = deps[0]
        print(f"Sample Departure: Trip {tid} at {dt}")
        
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        t_info = t_index.get(tid)
        print(f"Trip {tid} in tbr_trip_index: {t_info}")
        
        if t_info:
            t_start, t_count = t_info
            trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
            print(f"Trip Nodes for {tid}:")
            for i in range(t_count):
                node = trip_nodes[t_start + i]
                s = graph.stop_cache.get(node['stop_id'])
                print(f"  {i}: {s.code if s else node['stop_id']} (Arr: {datetime.fromtimestamp(node['arr_ts'])}, Dep: {datetime.fromtimestamp(node['dep_ts'])})")

    # Run actual find_routes
    found = await tbr.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
    print(f"\nFinal found: {len(found)} routes")

    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(debug_tbr())
