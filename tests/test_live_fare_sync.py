import asyncio
import os
import json
import logging
import sys
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.seat_verification import SeatVerificationService
from services.multi_layer_cache import multi_layer_cache

# --- MOCK JOURNEY WITH ESTIMATED FARES ---
ESTIMATED_JOURNEY = {
    "journey_id": "test_fare_sync",
    "total_cost": 500.0, # Initial estimation
    "legs": [
        {
            "train_number": "16378",
            "from_station_code": "PGT",
            "to_station_code": "BNC",
            "departure_time": "2026-03-04T08:00:00",
            "fare": 150.0, # Estimated
            "mode": "rail",
            "class_type": "2S"
        }
    ]
}

# --- MOCK API RESPONSE WITH DIFFERENT LIVE FARE ---
LIVE_API_RESPONSE = {
  "status": True,
  "data": [
    {
      "availablity_date": "4-3-2026",
      "availablity_status": "AVAILABLE-0197",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 197,
      "ticket_fare": 185,
      "catering_charge": 0,
      "total_fare": 185,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "4-3-2026",
      "current_status": "AVAILABLE-0197"
    }
  ]
}

async def test_live_fare_sync():
    print("STARTING LIVE FARE SYNC TEST")
    
    svc = SeatVerificationService()
    await multi_layer_cache.initialize()
    
    # Clone the journey to avoid side-effects between tests
    journey = json.loads(json.dumps(ESTIMATED_JOURNEY))
    
    print(f"1. Initial Journey Cost: {journey['total_cost']}")
    print(f"2. Initial Leg Fare: {journey['legs'][0]['fare']}")
    
    with patch.object(SeatVerificationService, "_execute_check_raw", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = LIVE_API_RESPONSE
        
        print("3. Running verify_journey (should sync live fares)...")
        is_available = await svc.verify_journey(journey)
        
        print(f"   [Result] Available: {is_available}")
        print(f"   [Result] Updated Total Cost: {journey['total_cost']}")
        print(f"   [Result] Updated Leg Fare: {journey['legs'][0]['fare']}")
        print(f"   [Result] Updated Leg Status: {journey['legs'][0]['availability_status']}")

        # ASSERTIONS
        assert is_available == True
        assert journey["total_cost"] == 185 # Overwritten by live API
        assert journey["legs"][0]["fare"] == 185 # Overwritten by live API
        assert journey["legs"][0]["availability_status"] == "AVAILABLE-0197"
        
    print("🏆 LIVE FARE SYNC VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_live_fare_sync())
