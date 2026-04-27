import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models import User
from database.models_redistribution import IncentiveCredit

logger = logging.getLogger(__name__)

class SovereignLedgerService:
    """
    Sovereign Intelligence Incentive Ledger Service.
    Handles the recording, tracking, and application of redistribution incentives.
    """

    @staticmethod
    def claim_incentive(
        db: Session, 
        user_id: str, 
        amount: float, 
        credit_type: str = "redistribution",
        description: str = "Incentive for system-optimal route choice",
        nudge_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records a new incentive claim for a user.
        Updates both the granular ledger and the user's aggregate balance.
        """
        try:
            # 1. Verify User
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                # If using Supabase ID, try lookup by that too
                user = db.query(User).filter(User.supabase_id == user_id).first()
            
            if not user:
                logger.error(f"User not found for incentive claim: {user_id}")
                raise ValueError("User not found")

            # 2. Create Ledger Entry
            credit = IncentiveCredit(
                credit_id=str(uuid.uuid4()),
                user_id=user.id,
                amount=amount,
                credit_type=credit_type,
                description=f"{description} (Nudge: {nudge_id})" if nudge_id else description,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=90), # 90 day validity
                status="active"
            )
            db.add(credit)

            # 3. Update User Balance (using bonus_credit_balance for incentives)
            user.bonus_credit_balance += int(amount)
            user.total_lifetime_credits += int(amount)
            
            db.commit()
            db.refresh(credit)

            logger.info(f"Incentive claimed: {amount} for user {user.id} (Nudge: {nudge_id})")
            
            return {
                "status": "success",
                "credit_id": credit.credit_id,
                "new_balance": user.bonus_credit_balance,
                "expires_at": credit.expires_at.isoformat()
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to claim incentive: {str(e)}")
            raise

    @staticmethod
    def get_wallet_summary(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Retrieves the user's Sovereign Wallet summary.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = db.query(User).filter(User.supabase_id == user_id).first()
            
        if not user:
            return {"error": "User not found"}

        # Get active credits
        active_credits = db.query(IncentiveCredit).filter(
            IncentiveCredit.user_id == user.id,
            IncentiveCredit.status == "active"
        ).all()

        return {
            "balance": user.credit_balance,
            "bonus_balance": user.bonus_credit_balance,
            "total_available": user.credit_balance + user.bonus_credit_balance,
            "lifetime_earned": user.total_lifetime_credits,
            "active_vouchers_count": len(active_credits),
            "credits": [
                {
                    "id": c.credit_id,
                    "amount": c.amount,
                    "type": c.credit_type,
                    "description": c.description,
                    "created_at": c.created_at.isoformat(),
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None
                } for c in active_credits
            ]
        }

    @staticmethod
    def apply_credit_to_booking(
        db: Session, 
        user_id: str, 
        amount: float, 
        booking_id: str
    ) -> Dict[str, Any]:
        """
        Applies credit balance to a specific booking.
        Prioritizes bonus_credit_balance over primary credit_balance.
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                user = db.query(User).filter(User.supabase_id == user_id).first()
                
            if not user:
                raise ValueError("User not found")

            total_available = user.credit_balance + user.bonus_credit_balance
            if total_available < amount:
                raise ValueError("Insufficient credit balance")

            # Apply from bonus first
            applied_from_bonus = min(user.bonus_credit_balance, amount)
            remaining_to_apply = amount - applied_from_bonus
            
            user.bonus_credit_balance -= int(applied_from_bonus)
            user.credit_balance -= int(remaining_to_apply)

            # Update specific ledger entries if necessary (FIFO)
            # For simplicity, we just update the aggregate here, but in production 
            # we'd mark specific IncentiveCredit rows as 'used'
            
            db.commit()
            
            return {
                "status": "applied",
                "amount_applied": amount,
                "remaining_bonus": user.bonus_credit_balance,
                "remaining_primary": user.credit_balance
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to apply credit: {str(e)}")
            raise
