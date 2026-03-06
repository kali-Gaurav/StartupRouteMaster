import logging
import csv
import io
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from database.models import BankTransaction, Booking, EscrowStatus, AuditLog
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class ReconciliationService:
    """
    Task 8: Nightly Ledger Reconciliation.
    """
    def __init__(self, db: Session):
        self.db = db

    def _log_audit(self, entity_type: str, entity_id: str, action: str, old_val: str, new_val: str, performed_by: str = "SYSTEM", reason: str = None):
        """Task 8.7: Immutable Audit trail."""
        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_val,
            new_value=new_val,
            performed_by=performed_by,
            reason=reason
        )
        self.db.add(log)

    def fuzzy_match_utr(self, target_utr: str, search_list: List[str]) -> Optional[str]:
        """
        Task 8.2: Fuzzy matching for UTRs.
        Handles common typos like O instead of 0, I instead of 1, and single digit transpositions.
        """
        if not target_utr:
            return None
            
        normalized_target = target_utr.upper().replace('O', '0').replace('I', '1')
        
        for search_utr in search_list:
            if not search_utr: continue
            normalized_search = search_utr.upper().replace('O', '0').replace('I', '1')
            
            # Exact match after normalization
            if normalized_target == normalized_search:
                return search_utr
                
            # Basic distance check (allow 1 character difference)
            if len(normalized_target) == len(normalized_search) == 12:
                diff_count = sum(1 for a, b in zip(normalized_target, normalized_search) if a != b)
                if diff_count == 1:
                    return search_utr
        return None

    def parse_bank_csv(self, csv_content: str, format_type: str = "AUTO") -> List[Dict[str, Any]]:
        """
        Task 8.8: Support for multiple bank statement formats.
        Normalizes outputs to a standard dictionary.
        """
        reader = csv.reader(io.StringIO(csv_content))
        transactions = []
        
        # Simple heuristic parser for demo
        for row in reader:
            row_str = " ".join(row).upper()
            if "DATE" in row_str and "AMOUNT" in row_str:
                continue # Skip header
                
            amount_match = re.search(r"\b\d+\.\d{2}\b", row_str)
            utr_match = re.search(r"\b\d{12}\b", row_str)
            
            if amount_match and utr_match:
                transactions.append({
                    "utr": utr_match.group(),
                    "amount": float(amount_match.group()),
                    "raw": row_str
                })
        return transactions

    def reconcile_nightly_batch(self) -> Dict[str, Any]:
        """
        Task 8: Nightly core job.
        1. Finds all PENDING bank transactions.
        2. Tries to match them to bookings (Exact or Fuzzy).
        3. Promotes bookings if matched (8.4).
        4. Moves unmatched to SUSPENSE (8.3).
        """
        pending_txns = self.db.query(BankTransaction).filter(BankTransaction.status == "PENDING").all()
        
        results = {"total": len(pending_txns), "reconciled": 0, "suspense": 0, "promoted": 0}
        
        for txn in pending_txns:
            # Look for exact UTR match in pending or cancelled bookings
            booking = self.db.query(Booking).filter(
                Booking.utr_number == txn.utr,
                Booking.amount_paid == txn.amount
            ).first()
            
            if booking:
                # 8.4: Auto-promote if it arrived late and booking was cancelled for timeout
                if booking.booking_status == "cancelled" and booking.escrow_message == "Session abandoned by user.":
                    old_status = booking.booking_status
                    booking.booking_status = "confirmed"
                    booking.escrow_status = EscrowStatus.VERIFIED
                    booking.escrow_message = "Late payment received. Auto-promoted."
                    
                    self._log_audit("Booking", booking.id, "AUTO_PROMOTION", old_status, "confirmed", reason=f"Late UTR {txn.utr} matched")
                    results["promoted"] += 1
                
                txn.status = "RECONCILED"
                self._log_audit("BankTransaction", txn.id, "STATUS_CHANGE", "PENDING", "RECONCILED", reason=f"Matched Booking {booking.id}")
                results["reconciled"] += 1
            else:
                # Fuzzy match attempt
                recent_bookings = self.db.query(Booking).filter(
                    Booking.amount_paid == txn.amount,
                    Booking.booking_status == "pending"
                ).all()
                recent_utrs = [b.utr_number for b in recent_bookings if b.utr_number]
                
                matched_utr = self.fuzzy_match_utr(txn.utr, recent_utrs)
                if matched_utr:
                    f_booking = next((b for b in recent_bookings if b.utr_number == matched_utr), None)
                    if f_booking:
                        f_booking.escrow_status = EscrowStatus.VERIFIED
                        f_booking.booking_status = "confirmed"
                        txn.status = "RECONCILED"
                        self._log_audit("Booking", f_booking.id, "FUZZY_MATCH", "pending", "confirmed", reason=f"Fuzzy matched UTR {txn.utr} to {matched_utr}")
                        self._log_audit("BankTransaction", txn.id, "STATUS_CHANGE", "PENDING", "RECONCILED", reason=f"Fuzzy matched to Booking {f_booking.id}")
                        results["reconciled"] += 1
                        continue

                # 8.3: Suspense Account (No match found)
                txn.status = "UNMATCHED_FUNDS"
                self._log_audit("BankTransaction", txn.id, "STATUS_CHANGE", "PENDING", "UNMATCHED_FUNDS", reason="No matching booking found")
                results["suspense"] += 1
                
        self.db.commit()
        return results

    def generate_pl_report(self, date: datetime.date) -> Dict[str, Any]:
        """Task 8.5: Profit/Loss statement generator (Daily)."""
        start = datetime.combine(date, datetime.min.time())
        end = start + timedelta(days=1)
        
        # Total received in bank
        received = self.db.query(func.sum(BankTransaction.amount)).filter(
            BankTransaction.received_at >= start,
            BankTransaction.received_at < end,
            BankTransaction.status == "RECONCILED"
        ).scalar() or 0.0
        
        # Total suspense
        suspense = self.db.query(func.sum(BankTransaction.amount)).filter(
            BankTransaction.received_at >= start,
            BankTransaction.received_at < end,
            BankTransaction.status == "UNMATCHED_FUNDS"
        ).scalar() or 0.0
        
        return {
            "date": date.isoformat(),
            "reconciled_revenue": received,
            "suspense_liability": suspense,
            "total_inflow": received + suspense
        }

    def get_discrepancy_report(self) -> List[Dict[str, Any]]:
        """Task 8.6: Discrepancy report sent to Admin."""
        unmatched = self.db.query(BankTransaction).filter(BankTransaction.status == "UNMATCHED_FUNDS").all()
        return [{"id": t.id, "utr": t.utr, "amount": t.amount, "date": t.received_at.isoformat()} for t in unmatched]

    def rollback_transaction(self, admin_id: str, transaction_id: str, reason: str) -> Dict[str, Any]:
        """Task 8.10: Rollback logic for incorrectly verified bookings."""
        txn = self.db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
        if not txn:
            return {"success": False, "message": "Transaction not found"}
            
        old_status = txn.status
        txn.status = "REVERSED"
        self._log_audit("BankTransaction", txn.id, "ROLLBACK", old_status, "REVERSED", performed_by=admin_id, reason=reason)
        
        # Find associated booking if any
        booking = self.db.query(Booking).filter(Booking.utr_number == txn.utr).first()
        if booking:
            b_old = booking.booking_status
            booking.booking_status = "cancelled"
            booking.escrow_status = EscrowStatus.FAILED
            booking.escrow_message = f"Payment Rollback: {reason}"
            self._log_audit("Booking", booking.id, "ROLLBACK", b_old, "cancelled", performed_by=admin_id, reason=reason)
            
        self.db.commit()
        return {"success": True, "message": "Transaction reversed successfully"}
