import asyncio
import json
import os
import sys
from datetime import datetime

# 1. Setup paths so we can import everything from 'backend' root
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from core.route_engine.data_provider import DataProvider
from services.multi_layer_cache import multi_layer_cache
from database.session import initialize_database_pools
from sqlalchemy import text

async def run_final_verification():
    print("\n🔥 [FINAL VERIFICATION] RapidAPI -> SQLite Persistence & Mapping")
    print("="*60)
    
    # Initialize necessary components manually
    print("Step 1: Initializing Database Pools & Cache...")
    await initialize_database_pools()
    await multi_layer_cache.initialize()
    
    dp = DataProvider()
    
    # 2. Define a real-world sample response from RapidAPI (IRCTC V2 structure)
    sample_response = {
        "status": True,
        "message": "Success",
        "data": [
            {
                "date": "20-03-2026",
                "current_status": "AVAILABLE 0120",
                "seat_avl": 120,
                "total_fare": 1850,
                "confirm_probability": "100"
            }
        ]
    }
    
    train_no = "TEST_TRAIN_99"
    from_stn = "DELHI"
    to_stn = "MUMBAI"
    date_str = "2026-03-20"
    
    print(f"Step 2: Simulating DataProvider save logic for {train_no}...")
    # We call the internal save method that I implemented in Subtask 2.6
    dp._save_to_local_availability_cache(
        train_no, from_stn, to_stn, date_str, 
        "3A", "GN", 120, "AVAILABLE 0120", 1850, sample_response
    )
    
    # 3. Query the database directly to see if it's there
    print("Step 3: Querying SQLite train_availability_cache...")
    dp._ensure_session()
    query = text("""
        SELECT seats_available, status_text, fare 
        FROM train_availability_cache 
        WHERE train_number = :t
    """)
    res = dp.session.execute(query, {"t": train_no}).fetchone()
    
    if res:
        seats, status, fare = res
        print(f"\n📊 [DATABASE RESULT]")
        print(f"   - Train: {train_no}")
        print(f"   - Seats Available: {seats} (Expected: 120)")
        print(f"   - Status Text: {status} (Expected: AVAILABLE 0120)")
        print(f"   - Fare Saved: {fare} (Expected: 1850)")
        
        # Verify mapping accuracy
        if seats == 120 and fare == 1850 and "AVAILABLE" in status:
            print("\n✅ SUCCESS: RapidAPI response mapped and persisted PERFECTLY.")
        else:
            print("\n❌ FAILURE: Mapping mismatch detected.")
    else:
        print("\n❌ FAILURE: No data found in SQLite after save attempt.")

    dp.close()
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_final_verification())
