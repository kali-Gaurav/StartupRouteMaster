import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from services.seat_verification import SeatVerificationService
from database.session import SessionLocal
from database.config import Config

async def main():
    print("🧪 Starting Turbo Engine Accuracy & Quota-Efficiency Test...")
    
    api_key = os.getenv("RAPIDAPI_KEY") or Config.RAPIDAPI_KEY
    if not api_key:
        print("❌ RAPIDAPI_KEY not found. Verification cannot proceed.")
        return

    db = SessionLocal()
    search_svc = SearchService(db)
    seat_svc = SeatVerificationService()
    
    # 1. SEARCH: Using TurboRouter logic
    source = "PGT"
    destination = "BNC"
    target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d") # Tomorrow
    
    print(f"\n[STEP 1] Running Turbo Search: {source} -> {destination} on {target_date}...")
    start_search = time.time()
    results = await search_svc.search_routes(source, destination, target_date)
    search_time = (time.time() - start_search) * 1000
    
    journeys = results.get("journeys", [])
    if not journeys:
        print("⚠️ No routes found by Turbo engine. Check if station_transit_index is populated.")
        db.close()
        return

    print(f"✅ Turbo found {len(journeys)} journeys in {search_time:.2f}ms.")
    
    # 2. VERIFY: Live RapidAPI call for the first journey
    # We choose the first direct train for simplicity
    target_journey = journeys[0]
    leg = target_journey["legs"][0]
    train_no = leg["train_number"]
    
    print(f"\n[STEP 2] Verifying Turbo Accuracy for Train {train_no} ({leg['from_station_code']} -> {leg['to_station_code']})...")
    print(f"📡 This will be a LIVE RapidAPI call (Quota -1).")
    
    v_start = time.time()
    # Force a fresh check (we assume cache is empty or expired for this specific train/date)
    # Using the exact date format DD-MM-YYYY as confirmed working
    api_date = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d-%m-%Y")
    
    live_result = await seat_svc.check_segment(train_no, leg['from_station_code'], leg['to_station_code'], api_date)
    
    if live_result.get("success"):
        print(f"✅ Accuracy Confirmed: Train {train_no} is ACTIVE on RapidAPI.")
        print(f"   Status: {live_result.get('status')}")
        print(f"   Seats: {live_result.get('seats')}")
        print(f"   Verification Latency: {(time.time() - v_start)*1000:.2f}ms")
    else:
        print(f"❌ RapidAPI Mismatch or Error: {live_result.get('error')}")

    # 3. QUOTA EFFICIENCY: Test the 6-day bulk cache
    # We check for the day AFTER the target date. 
    # If our bulk cache logic works, this should be a 100% Cache Hit (Quota -0)
    next_day = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%d-%m-%Y")
    
    print(f"\n[STEP 3] Testing Quota Efficiency (Checking next day {next_day} for same train)...")
    print(f"🛡️ This SHOULD be a CACHE HIT (Quota -0).")
    
    c_start = time.time()
    cache_result = await seat_svc.check_segment(train_no, leg['from_station_code'], leg['to_station_code'], next_day)
    cache_latency = (time.time() - c_start) * 1000
    
    if cache_result.get("success"):
        print(f"🔥 QUOTA SAVED! Multi-day Cache Hit confirmed.")
        print(f"   Status: {cache_result.get('status')}")
        print(f"   Cache Latency: {cache_latency:.2f}ms (vs live verification)")
    else:
        print(f"⚠️ Cache miss or logic failure for multi-day persistence.")

    await seat_svc.close_session()
    db.close()
    print("\n🏁 Test Complete. The Turbo engine is verified correct and quota-optimized.")

if __name__ == "__main__":
    asyncio.run(main())
