"""
Credit Service - User wallet and credit management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from database.models import User, Wallet, CreditTransaction

logger = logging.getLogger("credit_service")


class UnlockCreditService:
    """
    Service for managing user wallet credits.
    
    Features:
    - Wallet balance查询
    - Credit add/deduct
    - Transaction history
    - Wallet top-up
    """
    
    def __init__(self):
        pass
    
    def get_user_balance(
        self,
        db: Session,
        user_id: str
    ) -> float:
        """Get user's wallet balance."""
        try:
            result = db.query(Wallet).filter(
                Wallet.user_id == user_id
            ).first()
            
            return result.balance if result else 0.0
            
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return 0.0
    
    def add_credits(
        self,
        db: Session,
        user_id: str,
        amount: float,
        transaction_type: str = "topup",
        description: str = ""
    ) -> Dict[str, Any]:
        """Add credits to user wallet."""
        try:
            # Get or create wallet
            wallet = db.query(Wallet).filter(
                Wallet.user_id == user_id
            ).first()
            
            if not wallet:
                wallet = Wallet(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    balance=0.0,
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(wallet)
            
            # Store balance before
            balance_before = wallet.balance
            
            # Update balance
            wallet.balance += amount
            wallet.updated_at = datetime.now(timezone.utc)
            
            # Create transaction record
            transaction = CreditTransaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                wallet_id=wallet.id,
                transaction_type=transaction_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                reason=description,
                created_at=datetime.now(timezone.utc)
            )
            db.add(transaction)
            
            db.commit()
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "amount": amount,
                "new_balance": wallet.balance
            }
            
        except Exception as e:
            logger.error(f"Error adding credits: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def deduct_credits(
        self,
        db: Session,
        user_id: str,
        amount: float,
        transaction_type: str = "payment",
        description: str = ""
    ) -> Dict[str, Any]:
        """Deduct credits from user wallet."""
        try:
            # Get wallet
            wallet = db.query(Wallet).filter(
                Wallet.user_id == user_id
            ).first()
            
            if not wallet or wallet.balance < amount:
                return {
                    "success": False,
                    "error": "Insufficient balance"
                }
            
            # Store balance before
            balance_before = wallet.balance
            
            # Deduct amount
            wallet.balance -= amount
            wallet.updated_at = datetime.now(timezone.utc)
            
            # Create transaction record
            transaction = CreditTransaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                wallet_id=wallet.id,
                transaction_type=transaction_type,
                amount=-amount,
                balance_before=balance_before,
                balance_after=wallet.balance,
                reason=description,
                created_at=datetime.now(timezone.utc)
            )
            db.add(transaction)
            
            db.commit()
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "amount": amount,
                "new_balance": wallet.balance
            }
            
        except Exception as e:
            logger.error(f"Error deducting credits: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_transaction_history(
        self,
        db: Session,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get user's transaction history."""
        try:
            transactions = db.query(CreditTransaction).filter(
                CreditTransaction.user_id == user_id
            ).order_by(
                CreditTransaction.timestamp.desc()
            ).limit(limit).all()
            
            return [
                {
                    "id": t.id,
                    "type": t.transaction_type,
                    "amount": t.amount,
                    "balance_after": t.balance_after,
                    "reason": t.reason,
                    "created_at": t.timestamp.isoformat()
                }
                for t in transactions
            ]
            
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []
    
    def get_wallet_summary(
        self,
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """Get wallet summary for user."""
        balance = self.get_user_balance(db, user_id)
        transactions = self.get_transaction_history(db, user_id, limit=10)
        
        # Calculate totals
        total_credits = sum(
            t["amount"] for t in transactions 
            if t["amount"] > 0 and t["type"] == "topup"
        )
        total_spent = abs(sum(
            t["amount"] for t in transactions 
            if t["amount"] < 0
        ))
        
        return {
            "user_id": user_id,
            "current_balance": balance,
            "total_credits": total_credits,
            "total_spent": total_spent,
            "recent_transactions": transactions[:5]
        }


# Bundle packages for credit top-ups
BUNDLE_PACKS = {
    "BASIC_100": {"credits": 100, "price": 100, "bonus": 0},
    "BASIC_200": {"credits": 200, "price": 190, "bonus": 10},
    "STANDARD_500": {"credits": 500, "price": 450, "bonus": 50},
    "STANDARD_1000": {"credits": 1000, "price": 850, "bonus": 150},
    "PREMIUM_2000": {"credits": 2000, "price": 1600, "bonus": 400},
    "PREMIUM_5000": {"credits": 5000, "price": 3750, "bonus": 1250},
}

# Singleton instance
credit_service = UnlockCreditService()
unlock_credit_service = credit_service  # Alias for backward compatibility