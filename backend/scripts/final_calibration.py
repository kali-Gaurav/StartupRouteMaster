import asyncio
import json
import os
import sys
import aiohttp
from datetime import datetime

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.seat_verification import SeatVerificationService
from database.config import Config

async def test_direct_api(api_key):
    print("\n--- Direct API Test ---")
    url = "https://irctc1.p.rapidapi.com/api/v2/checkSeatAvailability"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "irctc1.p.rapidapi.com"
    }
    params = {
        "classType": "2S",
        "fromStationCode": "PGT",
        "quota": "GN",
        "toStationCode": "BNC",
        "trainNo": "16378",
        "date": "04-03-2026"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                print(f"HTTP Status: {resp.status}")
                data = await resp.json()
                print(f"API Response: {data}")
                return data
    except Exception as e:
        print(f"Direct API Error: {e}")
        return None

async def main():
    print("🚀 Final Calibration Check (PGT -> BNC, Train 16378)...")
    
    api_key = os.getenv("RAPIDAPI_KEY") or Config.RAPIDAPI_KEY
    if not api_key:
        print("❌ RAPIDAPI_KEY not found.")
        return

    # First test direct API to see raw response
    raw_res = await test_direct_api(api_key)
    
    print("\n--- Service Test ---")
    svc = SeatVerificationService()
    # PGT to BNC, Train 16378, March 4 2026
    result = await svc.check_segment("16378", "PGT", "BNC", "04-03-2026", class_type="2S")
    
    if result.get("success"):
        print(f"✅ Service Success! Status: {result.get('status')}")
    else:
        print(f"❌ Service Failed: {result.get('error')}")
    
    await svc.close_session()

if __name__ == "__main__":
    asyncio.run(main())
