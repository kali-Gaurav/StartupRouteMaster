import logging
import asyncio
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from database.models import User, NotificationToken, UserAlert, NotificationPreference

logger = logging.getLogger("notification-service")

class NotificationService:
    @staticmethod
    def send_alert(db: Session, user_id: str, title: str, body: str, alert_type: str = "SYSTEM", priority: int = 10, payload: dict = None):
        """
        [Task 46.1 & 46.4] Main orchestrator for delivering an alert.
        """
        # 1. Store in DB (In-App History)
        alert = UserAlert(
            user_id=user_id,
            title=title,
            body=body,
            alert_type=alert_type,
            priority=priority,
            payload=payload or {}
        )
        db.add(alert)
        db.commit()
        
        # 2. Find active channels
        tokens = db.query(NotificationToken).filter(
            NotificationToken.user_id == user_id,
            NotificationToken.is_active == True
        ).all()
        
        # 3. Check Preferences
        prefs = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        
        for t in tokens:
            try:
                # [Task 46.5] Priority & Preference Routing
                if alert_type == "PROMOTION" and prefs and not prefs.enable_promotions:
                    continue
                    
                if t.channel == "WEB_PUSH":
                    NotificationService._send_fcm(t.token, title, body, payload)
                elif t.channel == "TELEGRAM":
                    NotificationService._send_telegram(t.token, title, body)
                    
            except Exception as e:
                logger.error(f"Failed to deliver to {t.channel} for {user_id}: {e}")

    @staticmethod
    def _send_fcm(token: str, title: str, body: str, payload: dict = None):
        """
        [Task 46.2] Placeholder for Firebase Admin logic.
        """
        logger.info(f"📲 FCM Push Sent to {token[:10]}... | {title}")
        # firebase_admin.messaging.send(...) would go here

    @staticmethod
    def _send_telegram(chat_id: str, title: str, body: str):
        """
        [Task 46.3] Placeholder for Telegram Bot API.
        """
        logger.info(f"✈️ Telegram Sent to {chat_id} | {title}")
        # requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", ...)

    @staticmethod
    def get_user_notifications(db: Session, user_id: str, limit: int = 20) -> List[UserAlert]:
        """
        [Task 46.6] Fetch unread history for in-app center.
        """
        return db.query(UserAlert).filter(
            UserAlert.user_id == user_id
        ).order_by(UserAlert.timestamp.desc()).limit(limit).all()

notification_service = NotificationService()
