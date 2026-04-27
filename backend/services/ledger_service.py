import logging
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func, inspect
from database.models import User, Payment, Refund, Booking, PrecalculatedRoute, FinancialLedger
from datetime import datetime

logger = logging.getLogger("routemaster.ledger")

class LedgerService:
    """
    [Patent-Level] Unified Financial Ledger.
    Aggregates all user financial activity (Payments, Refunds, Karma) into a single stream.
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_user_ledger(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Unified Ledger Stream.
        Returns a time-sorted mixed list of all financial events.
        """
        # 1. Fetch Payments
        payments = self.db.query(Payment).filter(Payment.user_id == user_id).order_by(desc(Payment.created_at)).limit(limit).all()
        
        # 2. Fetch Refunds (via payments)
        refunds = self.db.query(Refund).join(Payment).filter(Payment.user_id == user_id).order_by(desc(Refund.created_at)).limit(limit).all()
        
        # 3. Aggregate into a common schema
        ledger = []
        
        for p in payments:
            ledger.append({
                "type": "PAYMENT",
                "id": p.id,
                "amount": p.amount,
                "status": p.status,
                "method": "RAZORPAY" if p.razorpay_payment_id else "UPI",
                "reference": p.razorpay_payment_id or p.merchant_vpa,
                "pnr": getattr(p.booking, "pnr_number", None),
                "created_at": p.created_at,
                "description": f"Route Unlock / Booking"
            })
            
        for r in refunds:
            ledger.append({
                "type": "REFUND",
                "id": r.id,
                "amount": 0, # Should find amount from associated payment
                "status": r.status,
                "reference": r.razorpay_refund_id,
                "created_at": r.created_at,
                "description": f"Refund for payment {r.payment_id}"
            })

        # Sort by date
        ledger.sort(key=lambda x: x["created_at"], reverse=True)
        return ledger[:limit]

    async def get_ppr_metrics(self) -> List[Dict[str, Any]]:
        """
        [Genius-Level] Returns the efficiency of each route corridor.
        PPR = (Total Revenue) / (Search-to-Booking Effort)
        """
        try:
            inspector = inspect(self.db.bind)
            columns = set()
            if inspector is not None and hasattr(inspector, "get_columns"):
                columns = {col["name"] for col in inspector.get_columns("precalculated_routes")}
        except Exception as exc:
            logger.warning("Unable to inspect precalculated_routes schema for PPR metrics: %s", exc)
            return []

        if "src" in columns and "dest" in columns:
            origin_expr = PrecalculatedRoute.src.label("origin")
            dest_expr = PrecalculatedRoute.dest.label("dest")
            group_by_expr = (PrecalculatedRoute.src, PrecalculatedRoute.dest)
        elif "route_data" in columns:
            origin_expr = PrecalculatedRoute.route_data["source"].as_string().label("origin")
            dest_expr = PrecalculatedRoute.route_data["destination"].as_string().label("dest")
            group_by_expr = ("origin", "dest")
        else:
            logger.warning("Skipping PPR metrics: precalculated_routes missing src/dest/route_data columns.")
            return []

        try:
            raw_data = self.db.query(
                origin_expr,
                dest_expr,
                func.sum(Payment.amount).label("total_revenue"),
                func.count(Booking.id).label("booking_count"),
            ).join(Booking, Booking.route_id == PrecalculatedRoute.id)\
             .join(Payment, Payment.booking_id == Booking.id)\
             .group_by(*group_by_expr).all()
        except Exception as exc:
            logger.warning("PPR metrics query failed: %s", exc)
            return []

        return [
            {
                "origin": r.origin,
                "dest": r.dest,
                "revenue": r.total_revenue,
                "efficiency": r.total_revenue / max(1, r.booking_count),
            }
            for r in raw_data
        ]

    def get_account_balance(self, account_type: str, user_id: Optional[str] = None) -> float:
        """Calculate net balance for the given ledger account."""
        db = self.db
        if db is None:
            raise ValueError("Database session is required")

        credit_query = db.query(func.coalesce(func.sum(FinancialLedger.amount), 0.0)).filter(
            FinancialLedger.credit_account == account_type
        )
        debit_query = db.query(func.coalesce(func.sum(FinancialLedger.amount), 0.0)).filter(
            FinancialLedger.debit_account == account_type
        )
        if user_id is not None:
            credit_query = credit_query.filter(FinancialLedger.user_id == user_id)
            debit_query = debit_query.filter(FinancialLedger.user_id == user_id)

        credited = credit_query.scalar() or 0.0
        debited = debit_query.scalar() or 0.0
        return float(credited - debited)

    def verify_ledger_integrity(self) -> bool:
        """Verify ledger hash chain integrity."""
        db = self.db
        if db is None:
            raise ValueError("Database session is required")

        try:
            entries = db.query(FinancialLedger).order_by(FinancialLedger.id.asc()).all()
            if not entries:
                return True

            current_hash = "GENESIS"
            for entry in entries:
                data = f"{entry.debit_account}|{entry.credit_account}|{entry.amount}|{entry.transaction_type}|{entry.user_id}|{current_hash}"
                expected_hash = hashlib.sha256(data.encode()).hexdigest()
                if str(entry.cumulative_hash) != expected_hash:
                    logger.error(f"Ledger integrity failed for entry {entry.id}")
                    return False
                current_hash = entry.cumulative_hash
            return True
        except Exception as exc:
            logger.error(f"Ledger integrity check failed: {exc}")
            return False

    async def record_transaction(self, db, debit_acc, credit_acc, amount, booking_id, agent_id):
        """Stub for settlement_service compatibility. Returns a dummy transaction object."""
        class DummyEntry:
            transaction_uuid = "DUMMY123456"
            id = transaction_uuid
        return DummyEntry()

ledger_service = lambda db: LedgerService(db)
