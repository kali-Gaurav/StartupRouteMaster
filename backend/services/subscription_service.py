from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database.models import Subscription
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Handles CRUD for the subscription table."""

    def __init__(self, db: Session):
        self.db = db

    def get_subscription(self, user_id: str) -> Subscription | None:
        return self.db.query(Subscription).filter(Subscription.user_id == user_id).first()

    def set_subscription(self, user_id: str, is_pro: bool, expires_at: datetime | None = None,
                         source: str = "razorpay", original_app_user_id: str | None = None):
        sub = self.get_subscription(user_id)
        if not sub:
            sub = Subscription(
                user_id=user_id,
                is_pro=is_pro,
                expires_at=expires_at,
                source=source,
                original_app_user_id=original_app_user_id
            )
            self.db.add(sub)
        else:
            sub.is_pro = is_pro
            sub.expires_at = expires_at
            sub.source = source
            if original_app_user_id:
                sub.original_app_user_id = original_app_user_id
            sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def clear_subscription(self, user_id: str):
        sub = self.get_subscription(user_id)
        if sub:
            self.db.delete(sub)
            self.db.commit()
            return True
        return False

    def is_active(self, user_id: str) -> bool:
        sub = self.get_subscription(user_id)
        if not sub or not sub.is_pro:
            return False
        if sub.expires_at and sub.expires_at < datetime.utcnow():
            # expired
            return False
        return True


subscription_service = SubscriptionService
