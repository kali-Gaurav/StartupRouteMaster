import logging
from typing import Optional
from sqlalchemy.orm import Session
from database.models import User, AuditLog
from services.credit_service import credit_service

logger = logging.getLogger("karma-service")

KARMA_VALUES = {
    "ROUTE_UNLOCK": 50,
    "AGENT_BOOKING_COMPLETED": 200,
    "STATION_HELP_REVIEW": 100, # My suggestion
    "REFERRAL_SIGNUP": 10,
    "REFERRAL_CONVERSION": 500, # Substantial reward
}

KARMA_MILESTONES = [500, 1000, 2500, 5000, 10000]

class KarmaService:
    @staticmethod
    def add_karma(db: Session, user_id: str, event_type: str, reason: Optional[str] = None) -> int:
        """
        Increments user karma score and checks for milestone bonuses.
        """
        points = KARMA_VALUES.get(event_type, 0)
        if points == 0: return 0

        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user: return 0

        prev_score = user.karma_score or 0
        user.karma_score = prev_score + points
        
        # Audit
        db.add(AuditLog(
            entity_type="User",
            entity_id=user_id,
            action="KARMA_ACCREDITATION",
            old_value=str(prev_score),
            new_value=str(user.karma_score),
            reason=reason or f"Earned {points} for {event_type}"
        ))

        # [Task 43.B HARDENING] Multi-Milestone Reward Logic
        # Check if the points jump the user across MULTIPLE milestones at once
        rewarded_credits = 0
        for m in KARMA_MILESTONES:
            if prev_score < m <= user.karma_score:
                rewarded_credits += 1
                logger.info(f"🏆 User {user_id} hit milestone {m}! Granting bonus credit.")
        
        # Add credits as a single transaction if multiple jumps occurred
        if rewarded_credits > 0:
            user.bonus_credit_balance += rewarded_credits
            # Log separate Audit for each (Optional, can be grouped)
            
        db.commit()
        return user.karma_score

    @staticmethod
    def initialize_referral(db: Session, user: User) -> str:
        """Generates a unique referral code if not exists."""
        if user.referral_code: return user.referral_code
        
        import random, string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        user.referral_code = code
        db.commit()
        return code

    @staticmethod
    def process_referral_conversion(db: Session, newly_converted_user_id: str):
        """
        [Task 43.C] Awards credits to referrer and referee.
        Triggered on first "Unlock" or "Booking".
        """
        user = db.query(User).filter(User.id == newly_converted_user_id).first()
        if not user or not user.referred_by_id or user.referral_status == "CONVERTED":
            return

        referrer_id = user.referred_by_id
        
        # [Task 43.C HARDENING] Anti-Fraud Check
        # Check 1: Suspicious Email Domain
        SUSPECT_DOMAINS = ["temp-mail.com", "guerrillamail.com", "10minutemail.com"]
        if user.email and any(domain in user.email for domain in SUSPECT_DOMAINS):
            logger.warning(f"🚫 Referral Fraud Block: Suspicious Referee Email {user.email}")
            return

        # Check 2: Same identity fingerprint (Implementation in Task 45: Advanced Security)
        # For now, placeholder verification for conversion delay
        
        # 1. Grant 1 Credit to Referrer
        from services.credit_service import credit_service
        # (Assuming we have a method for manual grant in Task 42)
        referrer = db.query(User).filter(User.id == referrer_id).first()
        if referrer:
            referrer.bonus_credit_balance += 1
            
        # 2. Grant 1 Credit to Referee
        user.bonus_credit_balance += 1
        user.referral_status = "CONVERTED"
        
        # 3. Add High Karma Points to Referrer
        KarmaService.add_karma(db, referrer_id, "REFERRAL_CONVERSION", f"Referral {newly_converted_user_id} converted.")
        
        db.commit()
        logger.info(f"🤝 Referral Loop Closed: {referrer_id} -> {newly_converted_user_id}")

karma_service = KarmaService()
