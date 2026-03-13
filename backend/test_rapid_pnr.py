import asyncio
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.pnr_service import pnr_status_service
from database.config import Config

async def test_rapid_pnr():
    print("\n--- RapidAPI PNR Client Verification ---")
    print(f"API Host: {Config.RAPIDAPI_HOST}")
    print(f"API Key: {Config.RAPIDAPI_KEY[:5]}...{Config.RAPIDAPI_KEY[-5:] if len(Config.RAPIDAPI_KEY) > 5 else ''}")
    
    # Test with a dummy but valid format PNR
    test_pnr = "1234567890"
    print(f"\nTesting PNR: {test_pnr}")
    
    res = await pnr_status_service.get_status(test_pnr)
    
    print("\nResponse Received:")
    print(json.dumps(res, indent=2))
    
    if res.get("success"):
        print("\n✅ SUCCESS: API call returned valid data.")
    elif "PNR Not found" in res.get("message", ""):
        print("\n✅ SUCCESS: API communication verified (Provider confirmed PNR not found).")
    else:
        print("\n❌ FAIL: API communication failed.")
    print("----------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(test_rapid_pnr())
