import hashlib
import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import FinancialLedger, User

logger = logging.getLogger("ledger-service")

class LedgerService:
    @staticmethod
    def record_transaction(
        db: Session, 
        debit_acc: str, 
        credit_acc: str, 
        amount: float, 
        transaction_type: str,
        user_id: str = None,
        metadata: dict = None
    ) -> FinancialLedger:
        """
        [Task 49.2 & 49.9] Atomic recording of a double-entry transaction with Hash Chain.
        """
        if amount <= 0: raise ValueError("Amount must be positive.")
        
        # 1. Get Previous Row Hash [49.9 Chain]
        prev_entry = db.query(FinancialLedger).order_by(FinancialLedger.id.desc()).first()
        prev_hash = prev_entry.cumulative_hash if prev_entry else "GENESIS"
        
        # 2. Create Entry
        entry = FinancialLedger(
            debit_account=debit_acc,
            credit_account=credit_acc,
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            metadata_json=metadata or {},
            previous_row_hash=prev_hash
        )
        
        # 3. Calculate Cumulative Hash
        data_to_hash = f"{debit_acc}|{credit_acc}|{amount}|{transaction_type}|{user_id}|{prev_hash}"
        entry.cumulative_hash = hashlib.sha256(data_to_hash.encode()).hexdigest()
        
        db.add(entry)
        db.commit()
        db.refresh(entry)
        
        logger.info(f"💰 Ledger Entry Created: {transaction_type} | {amount} INR | ID: {entry.id}")
        return entry

    @staticmethod
    def get_account_balance(db: Session, account_name: str, user_id: str = None) -> float:
        """
        [Task 49.4] Calculate balance via Double-Entry parity.
        Balance = (Sum of Debits) - (Sum of Credits)
        """
        query = db.query(func.sum(FinancialLedger.amount))
        if user_id: query = query.filter(FinancialLedger.user_id == user_id)
        
        debits = query.filter(FinancialLedger.debit_account == account_name).scalar() or 0.0
        credits = query.filter(FinancialLedger.credit_account == account_name).scalar() or 0.0
        
        return debits - credits

    @staticmethod
    def verify_ledger_integrity(db: Session) -> bool:
        """
        [Task 49.9] Audit the entire Hash Chain for tamper detection.
        """
        entries = db.query(FinancialLedger).order_by(FinancialLedger.id.asc()).all()
        current_hash = "GENESIS"
        
        for e in entries:
            # Re-calculate hash
            data = f"{e.debit_account}|{e.credit_account}|{e.amount}|{e.transaction_type}|{e.user_id}|{current_hash}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            
            if e.cumulative_hash != expected_hash:
                logger.critical(f"🛑 LEDGER TAMPER DETECTED AT ROW {e.id}!")
                return False
            
            current_hash = e.cumulative_hash
            
        return True

ledger_service = LedgerService()
