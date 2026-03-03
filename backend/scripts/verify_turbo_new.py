import asyncio
import json
import os
import sys
import aiohttp
from datetime import datetime, timedelta

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.turbo_router import TurboRouter
from services.realtime_ingestion.live_status_service import LiveStatusService
from database.config import Config

async def check_seat_availability_v2(api_key, train_no, from_code, to_code, date_str, class_type="2S", quota="GN"):
    """Corrected Seat Check according to user example using api/v2"""
    url = "https://irctc1.p.rapidapi.com/api/v2/checkSeatAvailability"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "irctc1.p.rapidapi.com"
    }
    # User's provided example used DD-MM-YYYY
    params = {
        "classType": class_type,
        "fromStationCode": from_code,
        "quota": quota,
        "toStationCode": to_code,
        "trainNo": train_no,
        "date": date_str
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    return {"success": False, "error": f"HTTP {resp.status}", "raw": text}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def main():
    print("🚀 Starting Turbo Verification (PGT -> BNC)...")
    
    api_key = os.getenv("RAPIDAPI_KEY") or Config.RAPIDAPI_KEY
    if not api_key:
        print("❌ RAPIDAPI_KEY not found.")
        return

    # 1. Setup Stations and Date
    source = "PGT"
    destination = "BNC"
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    # The user example showed DD-MM-YYYY for date: 04-03-2026
    # Tomorrow is indeed 2026-03-04 in this session context (Tuesday 3 March 2026)
    date_str = tomorrow.strftime("%d-%m-%Y")
    
    print(f"🔍 Searching routes for {source} -> {destination} on {date_str} using TurboRouter...")
    
    # 2. Generate Routes using TurboRouter
    router = TurboRouter()
    try:
        turbo_results = router.find_routes(source, destination, tomorrow, limit=5)
    except Exception as e:
        print(f"❌ Error during TurboRouter search: {e}")
        return

    if not turbo_results:
        print("⚠️ No routes found by TurboRouter.")
        return

    print(f"✨ Found {len(turbo_results)} routes.")
    
    # Save routes to file
    with open("generated_routes.json", "w") as f:
        json.dump(turbo_results, f, indent=4)
    print("💾 Generated routes saved to generated_routes.json")

    # 3. Verify Correctness using RapidAPI
    print("\n🧐 Verifying routes against live truth (RapidAPI api/v2)...")
    live_svc = LiveStatusService()
    
    verification_results = []
    
    for idx, route in enumerate(turbo_results):
        print(f"\n--- Route {idx+1} ---")
        route_status = {
            "route_index": idx + 1,
            "trains": [],
            "overall_status": "Valid"
        }
        
        for leg in route['legs']:
            train_no = leg['train_no']
            print(f"🚂 Checking Train {train_no} ({leg['from']} -> {leg['to']})...")
            
            # Seat Availability using api/v2 (User's correct request)
            # Defaulting to 2S for this test as per user example
            avail_data = await check_seat_availability_v2(api_key, train_no, leg['from'], leg['to'], date_str, class_type="2S")
            
            leg_valid = False
            avail_status = "Unknown"
            
            if avail_data and avail_data.get("status"):
                print("   ✅ RapidAPI api/v2 search successful.")
                # The user's provided JSON has "data" as a list
                avail_list = avail_data.get("data", [])
                if avail_list:
                    # Find matching date
                    # Note: RapidAPI sometimes returns "d-m-yyyy" (no leading zero) in "date" field
                    # e.g. "4-3-2026"
                    target_d = date_str.lstrip('0').replace('-0', '-')
                    day_match = next((item for item in avail_list if item.get("date") == target_d), avail_list[0])
                    avail_status = day_match.get("current_status", "N/A")
                    print(f"   🎫 Seats: {avail_status} (Fare: {day_match.get('total_fare', 'N/A')})")
                    leg_valid = True
                else:
                    print("   ⚠️ No availability data in list.")
            else:
                print(f"   ❌ RapidAPI Error: {avail_data.get('message', avail_data.get('error'))}")

            # Check Live Status (using rappid url as per config)
            live_status = "Unknown"
            delay = 0
            try:
                live = await live_svc.get_live_status(train_no)
                if live:
                    live_status = live.get("status_message", "Running")
                    delay = live.get("delay_minutes", 0)
                    print(f"   📡 Live Status: {live_status}, Delay: {delay}m")
            except Exception as e:
                print(f"   ⚠️ Live status error: {e}")

            route_status["trains"].append({
                "train_no": train_no,
                "leg_valid": leg_valid,
                "availability": avail_status,
                "live_status": live_status,
                "delay": delay,
                "raw_avail": avail_data
            })
            
            if not leg_valid:
                route_status["overall_status"] = "Invalid or No Confirmation from API"

        verification_results.append(route_status)

    # 4. Save Verification Report
    with open("verification_report.json", "w") as f:
        json.dump(verification_results, f, indent=4)
    print("\n✅ Verification complete. Report saved to verification_report.json")
    
    # Close sessions
    await live_svc.close_session()

if __name__ == "__main__":
    asyncio.run(main())
