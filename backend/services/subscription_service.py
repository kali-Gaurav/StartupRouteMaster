import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from database.models import Subscription, User, AuditLog, PlatformConfig

logger = logging.getLogger("subscription-service")

# New Config: 48 hour grace period for subscriptions
GRACE_PERIOD_DAYS = 2

PLAN_FEATURES = {
    "FREE": {"max_unlocks": 5, "agent_fee_discount": 0.0, "priority_support": False, "search_limit_per_hour": 10},
    "PRO": {"max_unlocks": 9999, "agent_fee_discount": 0.5, "priority_support": True, "search_limit_per_hour": 100},
    "ELITE": {"max_unlocks": 9999, "agent_fee_discount": 1.0, "priority_support": True, "search_limit_per_hour": 1000, "exclusive_routes": True}
}

class SubscriptionService:
    @staticmethod
    def is_active_pro(sub: Optional[Subscription]) -> bool:
        if not sub: return False
        if sub.plan_tier == "FREE": return False
        
        # [Task 41.E] Grace Period Logic
        if sub.expires_at:
            grace_deadline = sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS)
            if grace_deadline < datetime.utcnow():
                return False
        return True

    @staticmethod
    def grant_pro_trial(db: Session, user_id: str, karma_score: int) -> Subscription:
        """[Task 41.G] Pro-Trial activation for high-karma users."""
        if karma_score < 500:
            raise ValueError("Insufficient karma for trial.")
        
        return SubscriptionService.upgrade_user(db, user_id, "PRO", months=0, reason="PRO_TRIAL_KARMA_BOOST")

    @staticmethod
    def upgrade_user(db: Session, user_id: str, tier: str, months: int = 1, reason: str = None) -> Subscription:
        sub = SubscriptionService.get_user_subscription(db, user_id)
        now = datetime.utcnow()
        
        if not sub:
            sub = Subscription(user_id=user_id)
            db.add(sub)
            
        old_tier = sub.plan_tier
        sub.plan_tier = tier
        sub.is_pro = True if tier in ["PRO", "ELITE"] else False
        sub.features = PLAN_FEATURES[tier]
        
        # Expiry Logic
        if sub.expires_at and sub.expires_at > now:
            sub.expires_at += timedelta(days=30 * months)
        else:
            sub.expires_at = now + timedelta(days=30 * months)
            
        # Audit Log
        audit = AuditLog(
            entity_type="Subscription",
            entity_id=sub.id,
            action="TIER_UPGRADE",
            old_value=old_tier,
            new_value=tier,
            performed_by="SYSTEM",
            reason=reason or f"Upgraded to {tier} for {months} months."
        )
        db.add(audit)
        db.commit()
        db.refresh(sub)
        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def get_user_subscription(db: Session, user_id: str) -> Optional[Subscription]:
        return db.query(Subscription).filter(Subscription.user_id == user_id).first()

subscription_service = SubscriptionService()
