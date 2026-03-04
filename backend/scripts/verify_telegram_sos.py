import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.telegram_service import telegram_service
from database.config import Config

async def test_telegram_broadcast():
    print("--- Telegram Emergency Broadcast Verification ---")
    
    # 1. Check Configuration
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        print("[FAIL] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return

    # 2. Test Broadcast
    print(f"\n[Test 1] Testing SOS message dispatch to {Config.TELEGRAM_CHAT_ID}...")
    success = await telegram_service.broadcast_sos(
        user_name="Gaurav Nagar (Test)",
        lat=28.6428,
        lng=77.2190,
        telegram_ids=[Config.TELEGRAM_CHAT_ID]
    )
    
    if success:
        print("[PASS] Telegram SOS Broadcast sent successfully! Check your Telegram.")
    else:
        print("[FAIL] Broadcast failed.")

if __name__ == "__main__":
    asyncio.run(test_telegram_broadcast())
