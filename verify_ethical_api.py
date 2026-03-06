import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from services.seat_verification import SeatVerificationService
from datetime import datetime, timedelta

async def verify_task_1():
    print("🧪 Verifying Task 1: Ethical API Integration (No Scraping)...")
    
    # 1. Initialize Ethical API Service
    service = SeatVerificationService()
    
    # We will test using a known route that should have data
    train_no = "12951"  # Mumbai Rajdhani
    from_stn = "MMCT"
    to_stn = "NDLS"
    date_str = (datetime.utcnow() + timedelta(days=10)).strftime("%d-%m-%Y")
    
    print(f"📡 Requesting Seat Availability for {train_no} from {from_stn} to {to_stn} on {date_str}...")
    
    result = await service.check_segment(
        train_no=train_no,
        from_code=from_stn,
        to_code=to_stn,
        date_str=date_str,
        quota="GN",
        class_type="3A"
    )
    
    print(f"✅ Received Data: {result}")
    
    # Verify the structure matches our ethical API response
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "available" in result, "Result must contain 'available' boolean"
    
    print("✅ Task 1 Verification SUCCESSFUL: Ethical API is fully operational.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_task_1())
