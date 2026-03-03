import asyncio
import json
import os
import sys
import aiohttp
import logging
from datetime import datetime

# ensure info-level log messages are shown when script runs
logging.basicConfig(level=logging.INFO)

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.seat_verification import SeatVerificationService
from database.config import Config

async def capture_raw_data():
    print("🎯 Capturing Real-Time RapidAPI Response (Bypassing Cache)...")
    
    api_key = os.getenv("RAPIDAPI_KEY") or Config.RAPIDAPI_KEY
    if not api_key:
        print("❌ RAPIDAPI_KEY not found.")
        return

    svc = SeatVerificationService()
    
    # Parameters for the known working train
    train_no = "16378"
    from_code = "PGT"
    to_code = "BNC"
    date_str = "04-03-2026" # March 4, 2026
    quota = "GN"
    class_type = "2S"
    
    # We call the raw multi-version method directly to FORCE an API call and get the RAW JSON
    print(f"📡 Sending live request to RapidAPI for Train {train_no}...")
    # the helper now chooses the correct version automatically and logs it
    raw_response = await svc._execute_check_raw_multi(train_no, from_code, to_code, date_str, quota, class_type)
    
    if raw_response:
        print("✅ RAW DATA RECEIVED!")
        # Save the absolute raw response to a file for user inspection
        output_file = "captured_rapid_response.json"
        with open(output_file, "w") as f:
            json.dump(raw_response, f, indent=4)
        
        print(f"💾 The REAL RapidAPI JSON has been saved to: {os.path.abspath(output_file)}")
        print("\nPreview of the raw data:")
        print(json.dumps(raw_response, indent=2)[:500] + "...")
    else:
        print("❌ Failed to get a response from any RapidAPI version (v3/v2/v1).")

    await svc.close_session()

if __name__ == "__main__":
    asyncio.run(capture_raw_data())
