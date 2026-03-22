
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

async def debug_tbr_all_pairs():
    await container.get('db')
    await container.get('search')
    
    db = SessionTransit()
    departure_date = datetime(2026, 3, 21, 10, 0, 0)
    constraints = RouteConstraints(persona=Persona.STANDARD, max_results=100)
    
    graph = await route_engine._get_current_graph(departure_date)
    orchestrator = UnifiedRoutingOrchestrator(route_engine)
    tbr = orchestrator.tbr_router
    
    pairs = [
        ("NDLS", "MMCT"),
        ("MS", "MAS"),
        ("HWH", "NDLS"),
        ("SBC", "MAS"),
        ("BPL", "RKMP")
    ]
    
    from utils.station_utils import resolve_stations
    
    print(f"{'Pair':<15} | {'Deps':<6} | {'TBR Yield':<10} | {'TBR Nodes'}")
    print("-" * 50)
    
    for src_code, dst_code in pairs:
        src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
        if not src_stop or not dst_stop:
            print(f"{src_code + '->' + dst_code:<15} | FAILED TO RESOLVE")
            continue
            
        deps = graph.get_departures_from_stop(src_stop.id, departure_date, 1440)
        found = await tbr.find_routes(src_stop.id, dst_stop.id, departure_date, constraints, graph)
        
        t_index = getattr(graph.snapshot, 'tbr_trip_index', {})
        tbr_nodes_available = len(t_index) if t_index else 0
        
        print(f"{src_code + '->' + dst_code:<15} | {len(deps):<6} | {len(found):<10} | {tbr_nodes_available}")
        
        if len(found) == 0 and len(deps) > 0:
            print(f"  DEBUG: Investigating why {src_code}->{dst_code} is ZERO despite {len(deps)} departures.")
            
            # Check for Trip 1157 specifically if SBC->MAS
            target_tids = [deps[0][1]]
            if src_code == "SBC" and dst_code == "MAS":
                target_tids.append(1157)
            
            for sample_tid in target_tids:
                t_info = t_index.get(sample_tid)
                print(f"  Sample Trip {sample_tid} in TBR index: {t_info}")
                if t_info:
                    t_start, t_count = t_info
                    trip_nodes = getattr(graph.snapshot, 'tbr_trip_nodes', None)
                    dest_found_in_trip = False
                    src_idx = -1
                    dst_idx = -1
                    for i in range(t_count):
                        node = trip_nodes[t_start + i]
                        if node['stop_id'] == src_stop.id: src_idx = i
                        if node['stop_id'] == dst_stop.id: dst_idx = i
                    
                    print(f"  Trip {sample_tid}: src_idx={src_idx}, dst_idx={dst_idx}")
                    if src_idx != -1 and dst_idx != -1 and src_idx < dst_idx:
                        print(f"    VALID DIRECT ROUTE FOUND IN DATA FOR {sample_tid}!")
                    else:
                        print(f"    No valid forward path in trip {sample_tid}")

    await container.shutdown_all()

if __name__ == "__main__":
    asyncio.run(debug_tbr_all_pairs())
