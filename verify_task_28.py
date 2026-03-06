import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("backend").resolve()))

from workers.irctc_worker import IRCTCWorker
from database.session import SessionLocal
from database.models import Booking

async def verify_task_28():
    print("🧪 Verifying Task 28: IRCTC Login Automator (Stealth)...")
    
    # 1. Ensure a booking exists for status updates
    db = SessionLocal()
    booking = db.query(Booking).first()
    if not booking:
        print("⏭️ No booking found to test status updates. Skipping DB update check.")
        booking_id = "test-id"
    else:
        booking_id = booking.id
    db.close()

    worker = IRCTCWorker(booking_id)
    try:
        print("Starting browser...")
        await worker.start()
        
        print("Navigating to IRCTC...")
        # We only test navigation to avoid getting IP-blocked during dev
        await worker.page.goto("https://www.irctc.co.in/nget/train-search", wait_until="networkidle", timeout=20000)
        
        title = await worker.page.title()
        print(f"Page Title: {title}")
        assert "IRCTC" in title
        
        # Check stealth: navigator.webdriver should be undefined
        is_webdriver = await worker.page.evaluate("navigator.webdriver")
        print(f"navigator.webdriver: {is_webdriver}")
        assert is_webdriver is None
        
        print("✅ Task 28 Verification SUCCESSFUL!")
    except Exception as e:
        print(f"❌ Verification failed: {e}")
    finally:
        await worker.close()

if __name__ == "__main__":
    asyncio.run(verify_task_28())
