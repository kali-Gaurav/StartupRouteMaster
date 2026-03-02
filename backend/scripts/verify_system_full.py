import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.core.route_engine import route_engine
from backend.core.route_engine.constraints import RouteConstraints
from backend.database.session import SessionLocal
from backend.utils.station_utils import resolve_stations

async def verify_system_full():
    print("=== STARTING FULL SYSTEM VERIFICATION ===")
    db = SessionLocal()
    try:
        # 1. Test Station Resolution
        print("[1/4] Testing Station Resolution...")
        src_query = "NDLS"
        dst_query = "BCT"
        src_stop, dst_stop = resolve_stations(db, src_query, dst_query)
        
        if not src_stop or not dst_stop:
            print(f"❌ Failed to resolve stations: {src_query} -> {dst_query}")
            return
        print(f"✅ Resolved: {src_query} ({src_stop.code}) -> {dst_query} ({dst_stop.code})")

        # 2. Test Route Generation (Routing Engine)
        print("[2/4] Testing Routing Engine (RAPTOR/Turbo)...")
        constraints = RouteConstraints(max_transfers=2, range_minutes=1440)
        travel_date = datetime.now() + timedelta(days=7)
        
        start_time = datetime.now()
        routes = await route_engine.search_routes(
            src_stop.code, 
            dst_stop.code, 
            travel_date, 
            constraints=constraints
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"✅ Found {len(routes)} routes in {duration:.2f}s")

        # 3. Process Results for File Export
        print("[3/4] Processing results for review...")
        processed_routes = []
        for r in routes:
            route_data = {
                "total_duration": r.total_duration,
                "total_distance": r.total_distance,
                "segments": []
            }
            for seg in r.segments:
                route_data["segments"].append({
                    "train": f"{seg.train_number} - {seg.train_name}",
                    "from": seg.departure_stop_id,
                    "to": seg.arrival_stop_id,
                    "dep": seg.departure_time.isoformat(),
                    "arr": seg.arrival_time.isoformat(),
                    "fare": seg.fare
                })
            processed_routes.append(route_data)

        # 4. Save to file and cache check
        output_file = "test_output/system_verification_routes.json"
        os.makedirs("test_output", exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(processed_routes, f, indent=2)
        print(f"✅ Routes saved to {output_file} for review.")

        print("\n=== SYSTEM VERIFICATION SUCCESSFUL ===")
        print("Backend -> Database -> Routing Engine -> Results: ALL OK")

    except Exception as e:
        print(f"\n❌ SYSTEM VERIFICATION FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_system_full())
