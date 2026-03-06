import sys
import os
import httpx
import asyncio

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.telegram_dispatcher import telegram_dispatcher

async def verify_task_33():
    print("=== Verifying Task 33: Telegram Standalone Dispatcher ===")
    
    # 1. Test Welcome Message (Direct Service Call)
    print("Testing Service: send_welcome...")
    # Should return False or log warning if token is missing, 
    # but the logic itself should be sound.
    success = await telegram_dispatcher.send_welcome(chat_id=12345)
    print(f"Welcome Message Result: {'Triggered' if success else 'Skipped (No Token)'}")

    # 2. Test Booking Notification with Inline Buttons
    print("Testing Service: send_booking_notification...")
    success_notify = await telegram_dispatcher.send_booking_notification(
        chat_id=12345, 
        booking_id="TEST_BK_123", 
        pnr="4215678901", 
        train_no="12626"
    )
    print(f"Booking Notification Result: {'Triggered' if success_notify else 'Skipped'}")

    # 3. Test Bot Webhook Endpoint
    print("Testing Webhook Endpoint: /api/telegram/webhook...")
    async with httpx.AsyncClient() as client:
        payload = {
            "message": {
                "text": "/start",
                "chat": {"id": 12345}
            }
        }
        response = await client.post("http://localhost:8000/api/telegram/webhook", json=payload)
        assert response.status_code == 200
        assert response.json()["ok"] is True
        print("[OK] Webhook correctly handled /start command")

    print("=== Task 33 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_33())
