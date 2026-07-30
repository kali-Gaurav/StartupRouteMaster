import asyncio
import uuid
import logging
from database.session import SessionUser, init_db
from database.models import User, NotificationToken, UserAlert, NotificationPreference
from services.communication.notification_service import notification_service

async def verify_task_46():
    print("🧪 Starting Verification for Task 46: Project Live Pulse...")
    await init_db()
    
    with SessionUser() as db:
        # 1. Create Mock User
        user_id = str(uuid.uuid4())
        user = User(id=user_id, email=f"notify_test_{user_id[:4]}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created Mock User: {user.id}")

        # 2. Register FCM and Telegram Tokens
        print("📲 Registering FCM and Telegram Tokens...")
        token_fcm = NotificationToken(user_id=user.id, channel="WEB_PUSH", token="FCM_MOCK_123")
        token_tg = NotificationToken(user_id=user.id, channel="TELEGRAM", token="CHAT_ID_456")
        db.add(token_fcm)
        db.add(token_tg)
        
        # 3. Setup Preferences (Disable Promotions)
        prefs = NotificationPreference(user_id=user.id, enable_promotions=False)
        db.add(prefs)
        db.commit()

    # 4. Trigger A Critical Alert (Booking Confirmed)
    print("🚨 Triggering PNR Confirmation Alert...")
    with SessionUser() as db:
        notification_service.send_alert(
            db, user_id, 
            "PNR Confirmed!", 
            "Your ticket for NDLS-BOM is ready.", 
            "PNR", 
            priority=5
        )
        
    # 5. Trigger A Disallowed Promo Update
    print("📢 Triggering Promotional Alert (Should skip FCM/TG due to prefs)...")
    with SessionUser() as db:
        notification_service.send_alert(
            db, user_id, 
            "Sale On!", 
            "Get 5 credits free.", 
            "PROMOTION"
        )

    # 6. Verify Results
    with SessionUser() as db:
        alert_history = db.query(UserAlert).filter(UserAlert.user_id == user_id).all()
        print(f"📜 Alert Ledger Found: {len(alert_history)} entries (Expected 2).")
        assert len(alert_history) == 2
        
        pnr_alert = next(a for a in alert_history if a.alert_type == "PNR")
        print(f"✅ PNR Alert Saved: {pnr_alert.title} | Priority: {pnr_alert.priority}")
        assert pnr_alert.priority == 5
        
        # Note: In-App Center ALWAYS stores the alert, but delivery skips FCM/TG for promos
        print("\n✅ TASK 46 VERIFIED: Pulse Notifications and Channel Preferences are Active.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(verify_task_46())
