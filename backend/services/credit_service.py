import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from database.models import User, CreditTransaction, AuditLog

logger = logging.getLogger("credit-service")

BUNDLE_PACKS = {
    "STARTER_5": {"credits": 5, "price": 199},   # ₹39.8 per credit
    "VALUE_10": {"credits": 10, "price": 349},  # ₹34.9 per credit
    "PRO_50": {"credits": 50, "price": 1499},   # ₹29.98 per credit (BEST VALUE)
}

class UnlockCreditService:
    @staticmethod
    def get_user_balance(db: Session, user_id: str) -> Dict[str, int]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user: return {"total": 0, "paid": 0, "bonus": 0}
        return {
            "total": user.credit_balance + user.bonus_credit_balance,
            "paid": user.credit_balance,
            "bonus": user.bonus_credit_balance
        }

    @staticmethod
    def top_up_credits(db: Session, user_id: str, bundle_id: str, payment_id: str) -> bool:
        """
        [Task 42.B] Adds credits to user account upon successful payment.
        """
        bundle = BUNDLE_PACKS.get(bundle_id)
        if not bundle:
            raise ValueError(f"Invalid bundle ID: {bundle_id}")

        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user: return False

        # [Task 43.D] Karma-Based Discount (Suggestion: Top scorers get 10% off)
        discount = 0.0
        if user.karma_score > 5000:
            discount = 0.10 # 10%
        elif user.karma_score > 1000:
            discount = 0.05 # 5%
            
        final_price = round(bundle["price"] * (1 - discount), 2)
        logger.info(f"Karma Discount Applied: {discount*100}% | New Price: {final_price}")

        # Top-up credits
        credits_to_add = bundle["credits"]
        
        # Audit Ledger
        old_balance = user.credit_balance
        user.credit_balance += credits_to_add
        user.total_lifetime_credits += credits_to_add
        
        tx = CreditTransaction(
            user_id=user_id,
            amount=credits_to_add,
            transaction_type="PURCHASE",
            balance_before=old_balance,
            balance_after=user.credit_balance,
            reference_entity_id=payment_id
        )
        db.add(tx)
        
        # [Task 42.E] First-time bonus logic
        if user.total_lifetime_credits <= credits_to_add:
            bonus = 1 # 1 free credit for first purchase
            user.bonus_credit_balance += bonus
            db.add(CreditTransaction(
                user_id=user_id,
                amount=bonus,
                transaction_type="BONUS",
                balance_before=0,
                balance_after=bonus,
                reference_entity_id=payment_id
            ))
            logger.info(f"Awarded First-Purchase Bonus to {user_id}")

        db.commit()
        logger.info(f"User {user_id} topped up {credits_to_add} via {bundle_id}")
        return True

    @staticmethod
    def consume_credit(db: Session, user_id: str, booking_id: str) -> bool:
        """
        [Task 42.C] Core Consumption Logic. Deducts 1 token.
        Priority: 1. Bonus 2. Paid
        """
        user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user or (user.credit_balance + user.bonus_credit_balance < 1):
            return False

        # --- MOMENTUM BONUS Logic (Gaurav Suggestion) ---
        # If user consumed last credit < 24 hours ago, check for "Speed Unlock"
        last_tx = db.query(CreditTransaction).filter(
            CreditTransaction.user_id == user_id, 
            CreditTransaction.transaction_type == "CONSUMPTION"
        ).order_by(CreditTransaction.timestamp.desc()).first()
        
        if last_tx and (datetime.utcnow() - last_tx.timestamp) < timedelta(hours=24):
            # Potential streak detection (Implementation logic in Task 43)
            pass

        # Deduction with Priority
        if user.bonus_credit_balance > 0:
            user.bonus_credit_balance -= 1
        else:
            user.credit_balance -= 1

        db.add(CreditTransaction(
            user_id=user_id,
            amount=-1,
            transaction_type="CONSUMPTION",
            balance_before=UnlockCreditService.get_user_balance(db, user_id)["total"] + 1,
            balance_after=UnlockCreditService.get_user_balance(db, user_id)["total"],
            reference_entity_id=booking_id
        ))
        
        db.commit()
        return True

credit_service = UnlockCreditService()
