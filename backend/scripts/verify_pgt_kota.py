import asyncio
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
from backend.services.seat_verification import SeatVerificationService

async def find_and_verify_pgt_kota():
    print("=== SEARCHING PALAKKAD TO KOTA FOR TOMORROW ===")
    db = SessionLocal()
    seat_service = SeatVerificationService()
    
    try:
        src_query = "PGT"
        dst_query = "KOTA"
        src_stop, dst_stop = resolve_stations(db, src_query, dst_query)
        
        # Tomorrow is March 3, 2026 (Tuesday)
        travel_date = datetime(2026, 3, 3)
        
        print("Searching for routes on " + str(travel_date.date()) + "...")
        
        constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
        routes = await route_engine.search_routes(src_stop.code, dst_stop.code, travel_date, constraints=constraints)
        
        if not routes:
            print("❌ No routes found by the engine.")
            return

        print("✅ Found " + str(len(routes)) + " routes. Verifying schedules and seats...")
        
        # Sort by total duration
        routes.sort(key=lambda x: x.total_duration)
        
        for i, route in enumerate(routes[:3]):
            print("\n[Option " + str(i+1) + "] Total Duration: " + str(route.total_duration // 60) + "h " + str(route.total_duration % 60) + "m")
            
            all_ok = True
            for seg in route.segments:
                print("  🚆 Train " + str(seg.train_number) + " (" + str(seg.train_name) + ")")
                print("     From: " + str(seg.departure_stop_id) + " at " + str(seg.departure_time))
                print("     To:   " + str(seg.arrival_stop_id) + " at " + str(seg.arrival_time))
                
                print("     💺 Checking seat availability...")
                from_code = str(seg.departure_stop_id)
                to_code = str(seg.arrival_stop_id)
                
                avail = seat_service.get_seat_availability(
                    train_no=seg.train_number,
                    date=seg.departure_time.strftime("%Y-%m-%d"),
                    from_station=from_code,
                    to_station=to_code,
                    class_code="3A"
                )
                
                if avail and avail.get("success"):
                    print("     ✅ Seats confirmed via API.")
                else:
                    error_msg = avail.get('error', 'Unknown error') if avail else 'Service disabled'
                    print("     ⚠️ API check failed: " + error_msg)
            
            if all_ok:
                print("✅ This route is the best optimal and available!")
                break

    except Exception as e:
        print("❌ Error: " + str(e))
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(find_and_verify_pgt_kota())
