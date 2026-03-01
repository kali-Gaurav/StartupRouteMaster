import asyncio
import os
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch

# Configure logging to see our new DEBUG statements
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to sys.path
import sys
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.seat_verification import SeatVerificationService
from services.multi_layer_cache import multi_layer_cache, AvailabilityQuery
from database.session import SessionLocal
from database.models import TrainAvailabilityCache

# --- MOCK DATA FROM USER ---
USER_API_RESPONSE = {
  "status": True,
  "message": "Success",
  "timestamp": 1772368865898,
  "data": [
    {
      "availablity_date": "4-3-2026",
      "availablity_status": "AVAILABLE-0197",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 197,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "4-3-2026",
      "current_status": "AVAILABLE-0197"
    },
    {
      "availablity_date": "5-3-2026",
      "availablity_status": "AVAILABLE-0240",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 240,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "5-3-2026",
      "current_status": "AVAILABLE-0240"
    },
    {
      "availablity_date": "6-3-2026",
      "availablity_status": "AVAILABLE-0231",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 231,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "6-3-2026",
      "current_status": "AVAILABLE-0231"
    },
    {
      "availablity_date": "7-3-2026",
      "availablity_status": "AVAILABLE-0220",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 220,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "7-3-2026",
      "current_status": "AVAILABLE-0220"
    },
    {
      "availablity_date": "8-3-2026",
      "availablity_status": "AVAILABLE-0048",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 48,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "8-3-2026",
      "current_status": "AVAILABLE-0048"
    },
    {
      "availablity_date": "9-3-2026",
      "availablity_status": "AVAILABLE-0274",
      "seat_avl_text": "AVAILABLE",
      "seat_avl": 274,
      "ticket_fare": 175,
      "catering_charge": 0,
      "total_fare": 175,
      "last_updated_at": "2026-03-01T18:11:05+05:30",
      "alt_cnf_seat": False,
      "date": "9-3-2026",
      "current_status": "AVAILABLE-0274"
    }
  ]
}

async def test_production_caching():
    print("\n--- STARTING PRODUCTION CACHING TEST (DEBUG MODE) ---")
    
    svc = SeatVerificationService()
    train_no = "16378"
    from_stn = "PGT"
    to_stn = "BNC"
    quota = "GN"
    cls = "2S"
    test_date = "2026-03-04" 
    
    await multi_layer_cache.initialize()
    
    print(f"1. Cleaning cache for {train_no}...")
    db = SessionLocal()
    try:
        db.query(TrainAvailabilityCache).filter(TrainAvailabilityCache.train_number == train_no).delete()
        db.commit()
    except Exception as e:
        print(f"   Error cleaning DB: {e}")
        db.rollback()
    finally:
        db.close()
    
    # 2. Mock the API call and DISABLE the background task in check_segment
    # We want to call _persist_bulk_availability manually and AWAIT it so we see where it hangs.
    with patch.object(SeatVerificationService, "_execute_check_raw", new_callable=AsyncMock) as mock_api, \
         patch("asyncio.create_task") as mock_task: # Disable background task
        
        mock_api.return_value = USER_API_RESPONSE

        print(f"2. REQUEST 1: Checking availability for {test_date}")
        result = await svc.check_segment(train_no, from_stn, to_stn, test_date, quota, cls)
        
        print(f"   Request 1 Done. status: {result.get('status')}")

        # 3. EXPLICITLY AWAIT PERSISTENCE
        print("3. Manually awaiting bulk persistence (monitoring for hangs)...")
        try:
            # Set a timeout for the DB operation
            await asyncio.wait_for(
                svc._persist_bulk_availability(
                    train_no, from_stn, to_stn, quota, cls, USER_API_RESPONSE["data"]
                ),
                timeout=30.0
            )
            print("   ✅ Persistence finished successfully.")
        except asyncio.TimeoutError:
            print("   ❌ TIMEOUT: Bulk persistence took more than 30 seconds. Database might be locked or slow.")
            return

    # 4. Check Redis for an ADJACENT date
    adjacent_date = "2026-03-05"
    print(f"4. REQUEST 2: Checking availability for {adjacent_date} (Expected: REDIS HIT)")
    
    with patch.object(SeatVerificationService, "_execute_check_raw", side_effect=Exception("API SHOULD NOT BE CALLED")):
        result2 = await svc.check_segment(train_no, from_stn, to_stn, adjacent_date, quota, cls)
        assert result2["seats"] == 240
        print(f"   🔥 REDIS HIT SUCCESS: Seats: {result2['seats']}")

    # 5. Verify Postgres Persistence
    print("5. Verifying Postgres Persistence...")
    db = SessionLocal()
    cached_days = db.query(TrainAvailabilityCache).filter(
        TrainAvailabilityCache.train_number == train_no
    ).all()
    
    print(f"   📊 Found {len(cached_days)} days in Postgres.")
    assert len(cached_days) >= 6
    db.close()

    print("\n🏆 ALL PRODUCTION CACHING TESTS PASSED!")

if __name__ == "__main__":
    try:
        asyncio.run(test_production_caching())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
