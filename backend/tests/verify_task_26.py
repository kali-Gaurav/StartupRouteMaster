import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_structures import Route, RouteSegment
from services.search_service import SearchService
from database.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_task_26")

async def verify_task_26():
    print("\n>>> Verifying Task 26: Quota-Specific Searching (Tatkal)")
    
    db = SessionLocal()
    service = SearchService(db)
    
    # 1. Mock DataProvider to capture the 'quota' argument
    # We want to see if 'TQ' reaches the verify_seat_availability_unified method
    captured_quota = None
    
    async def mock_verify_seat(*args, **kwargs):
        nonlocal captured_quota
        captured_quota = kwargs.get('quota')
        return {"status": "verified", "available_seats": 5}
        
    service.data_provider.verify_seat_availability_unified = AsyncMock(side_effect=mock_verify_seat)
    service.data_provider.verify_fare_unified = AsyncMock(return_value={"total_fare": 1200.0})
    
    # 2. Run a search with 'TQ' quota
    source, dest, date_str = "PGT", "KOTA", "2026-03-08"
    print(f"  Searching {source}->{dest} with quota='TQ'...")
    
    await service.search_routes(source, dest, date_str, quota="TQ")
    
    print(f"  Captured Quota in DataProvider: '{captured_quota}'")
    
    if captured_quota == "TQ":
        print("\n✅ TASK 26 VERIFIED: Quota parameter successfully threaded to verification layer.")
        return True
    else:
        print(f"❌ FAILURE: Quota mismatch. Expected 'TQ', got '{captured_quota}'")
        return False

if __name__ == "__main__":
    asyncio.run(verify_task_26())
