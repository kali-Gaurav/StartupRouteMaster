import asyncio
import os
import json
import logging
import uuid
import sys
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch

# Configure logging to see our new DEBUG statements
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.seat_verification import SeatVerificationService
from services.multi_layer_cache import multi_layer_cache, AvailabilityQuery
from database.session import SessionLocal
from database.models import TrainAvailabilityCache

# --- MOCK DATA FOR 2S (Second Sitting) ---
MOCK_2S_RESPONSE = {
  "status": True,
  "data": [
    {"date": "4-3-2026", "current_status": "AVAILABLE-0197", "seat_avl": 197, "total_fare": 175},
    {"date": "5-3-2026", "current_status": "AVAILABLE-0240", "seat_avl": 240, "total_fare": 175}
  ]
}

# --- MOCK DATA FOR SL (Sleeper) ---
MOCK_SL_RESPONSE = {
  "status": True,
  "data": [
    {"date": "4-3-2026", "current_status": "RLWL15/WL10", "seat_avl": 0, "total_fare": 450},
    {"date": "5-3-2026", "current_status": "AVAILABLE-0012", "seat_avl": 12, "total_fare": 450}
  ]
}

async def test_multi_class_caching():
    print("STARTING MULTI-CLASS PRODUCTION CACHING TEST")
    
    svc = SeatVerificationService()
    train_no = "16378"
    from_stn = "PGT"
    to_stn = "BNC"
    quota = "GN"
    test_date = "2026-03-04" 
    
    await multi_layer_cache.initialize()
    
    # 1. Clean DB
    print(f"1. Cleaning database for train {train_no}...")
    db = SessionLocal()
    db.query(TrainAvailabilityCache).filter(TrainAvailabilityCache.train_number == train_no).delete()
    db.commit()
    db.close()
    
    # 2. Search for 2S
    print("2. Searching for class: 2S (Expect API Call)")
    with patch.object(SeatVerificationService, "_execute_check_raw", new_callable=AsyncMock) as mock_api, \
         patch("asyncio.create_task") as mock_task:
        
        mock_api.return_value = MOCK_2S_RESPONSE
        res_2s = await svc.check_segment(train_no, from_stn, to_stn, test_date, quota, "2S")
        
        print(f"   [2S Result] Status: {res_2s['status']}, Fare: {res_2s['fare']}")
        assert res_2s["seats"] == 197
        assert mock_api.call_count == 1
        
        # Manually persist to simulate background task finishing
        await svc._persist_bulk_availability(train_no, from_stn, to_stn, quota, "2S", MOCK_2S_RESPONSE["data"])

    # 3. Search for SL (Same Train, Same Date, DIFFERENT CLASS)
    print("3. Searching for class: SL (Expect NEW API Call - Cache must be separate)")
    with patch.object(SeatVerificationService, "_execute_check_raw", new_callable=AsyncMock) as mock_api, \
         patch("asyncio.create_task") as mock_task:
        
        mock_api.return_value = MOCK_SL_RESPONSE
        res_sl = await svc.check_segment(train_no, from_stn, to_stn, test_date, quota, "SL")
        
        print(f"   [SL Result] Status: {res_sl['status']}, Fare: {res_sl['fare']}")
        assert res_sl["seats"] == 0
        assert "WL" in res_sl["status"]
        assert mock_api.call_count == 1
        
        await svc._persist_bulk_availability(train_no, from_stn, to_stn, quota, "SL", MOCK_SL_RESPONSE["data"])

    # 4. Verify Adjacent Day Hits for BOTH classes
    print("4. Verifying Cache for Adjacent Day (March 5th)")
    
    with patch.object(SeatVerificationService, "_execute_check_raw", side_effect=Exception("API ERROR")):
        # Check 2S for next day
        hit_2s = await svc.check_segment(train_no, from_stn, to_stn, "2026-03-05", quota, "2S")
        print(f"   [2S Next Day Hit] Seats: {hit_2s['seats']} (Expected: 240)")
        assert hit_2s["seats"] == 240
        
        # Check SL for next day
        hit_sl = await svc.check_segment(train_no, from_stn, to_stn, "2026-03-05", quota, "SL")
        print(f"   [SL Next Day Hit] Seats: {hit_sl['seats']} (Expected: 12)")
        assert hit_sl["seats"] == 12

    # 5. Final DB Check
    print("5. Checking Database Records...")
    db = SessionLocal()
    records = db.query(TrainAvailabilityCache).filter(TrainAvailabilityCache.train_number == train_no).all()
    print(f"   Total DB Records: {len(records)} (Expected: 4 - 2 days for each class)")
    assert len(records) == 4
    for r in records:
        print(f"   - {r.journey_date} | Class: {r.class_type} | Status: {r.status_text}")
    db.close()

    print("🏆 MULTI-CLASS CACHING VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_multi_class_caching())
