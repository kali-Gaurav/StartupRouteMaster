import asyncio
import logging
import time
from datetime import datetime, date
from database.session import SessionLocal
from database.models import Stop, Trip, Segment
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from core.redis import redis_client

# Suppress overly noisy logs to focus on our audit prints
logging.getLogger("core.route_engine").setLevel(logging.WARNING)

async def deep_graph_audit():
    print("="*60)
    print("DEEP GRAPH AND ROUTE GENERATION AUDIT")
    print("="*60)

    from core.route_engine.builder import TransitSessionLocal
    db = TransitSessionLocal()
    engine = RailwayRouteEngine()
    
    target_date = datetime(2026, 3, 11, 8, 0, 0) # A Wednesday
    print(f"1. Target Date: {target_date}")

    # --- A. Check Database Base Integrity ---
    abr = db.query(Stop).filter(Stop.stop_id == 'ABR').first()
    adi = db.query(Stop).filter(Stop.stop_id == 'ADI').first()
    
    if not abr or not adi:
        print("CRITICAL: Stations ABR or ADI not found in DB.")
        return
        
    print(f"2. Stations Found: ABR (ID: {abr.id}), ADI (ID: {adi.id})")
    
    # Check if any segments exist in the DB for ABR
    db_segs = db.query(Segment).filter(Segment.source_station_id == str(abr.id)).count()
    print(f"3. DB Segments originating from ABR: {db_segs}")

    # --- B. Build Graph & Inspect Memory ---
    print("--- BUILDING GRAPH ---")
    start_time = time.time()
    graph = await engine._get_current_graph(target_date)
    build_time = time.time() - start_time
    
    snapshot = graph.snapshot
    print(f"Graph Build Time: {build_time:.2f}s")
    print(f"Total Stops in Graph: {len(snapshot.stop_cache)}")
    print(f"Total Trips in Graph: {len(snapshot.trip_segments)}")
    
    # --- C. Inspect Graph Connectivity ---
    deps_abr = snapshot.departures_by_stop.get(abr.id, [])
    print("--- GRAPH CONNECTIVITY CHECK ---")
    print(f"Departures from ABR in Graph Memory: {len(deps_abr)}")
    
    if len(deps_abr) > 0:
        sample_trip_id = deps_abr[0][1]
        print(f"Sample Trip ID from ABR: {sample_trip_id}")
        
        # Trace this trip
        trip_segs = snapshot.trip_segments.get(sample_trip_id, [])
        print(f"Segments in Trip {sample_trip_id}: {len(trip_segs)}")
        
        # Check if ADI is in this trip
        adi_found = False
        for i, seg in enumerate(trip_segs):
            if seg.arrival_stop_id == adi.id:
                print(f"  -> Found ADI at segment index {i}! (Arrival: {seg.arrival_time})")
                adi_found = True
                break
        if not adi_found:
            print("  -> ADI is NOT in this trip's sequence.")
    else:
        print("FATAL: ABR has 0 departures in the generated graph. Route search will always fail.")
        
        # Let's debug WHY it has 0 departures.
        print("--- DEBUGGING ZERO DEPARTURES ---")
        # Find active services
        from core.route_engine.builder import GraphBuilder
        builder = GraphBuilder(None)
        service_ids = builder._get_active_service_ids(db, target_date)
        print(f"Active Service IDs on {target_date.date()}: {service_ids[:5]} (Total: {len(service_ids)})")
        
        # Check if trip 2582 (ABR->ADI) is in these services
        trip_2582 = db.query(Trip).filter(Trip.id == 2582).first()
        if trip_2582:
            print(f"Trip 2582 Service ID: {trip_2582.service_id}")
            if trip_2582.service_id in service_ids:
                print("Trip 2582 service IS active.")
            else:
                print("Trip 2582 service IS NOT active today.")
                
            # Check segments for trip 2582
            segs_2582 = db.query(Segment).filter(Segment.trip_id == 2582).all()
            print(f"Segments in DB for Trip 2582: {len(segs_2582)}")
            if len(segs_2582) > 0:
                print(f"First segment type: src={type(segs_2582[0].source_station_id)} dst={type(segs_2582[0].dest_station_id)}")

    # --- D. Execute Route Search ---
    print("--- EXECUTING RAPTOR SEARCH ---")
    constraints = RouteConstraints(max_transfers=1)
    start_search = time.time()
    routes = await engine.search_routes(abr.stop_id, adi.stop_id, target_date, constraints=constraints)
    search_time = time.time() - start_search
    
    print(f"Search Time: {search_time:.3f}s")
    print(f"Routes Found: {len(routes)}")
    
    if routes:
        best_route = routes[0]
        print(f"BEST ROUTE:")
        print(f"Duration: {best_route.total_duration} mins")
        print(f"Cost: {best_route.total_cost}")
        print(f"Transfers: {len(best_route.transfers)}")
        print(f"Score: {best_route.score:.2f}")
        for seg in best_route.segments:
            print(f"  {seg.train_number} | {seg.departure_code} ({seg.departure_time.strftime('%H:%M')}) -> {seg.arrival_code} ({seg.arrival_time.strftime('%H:%M')})")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(deep_graph_audit())
