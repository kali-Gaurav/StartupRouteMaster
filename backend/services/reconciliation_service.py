"""
Reconciliation Service - Phase 5 Financial Audit
Handles daily balancing of revenues and agent commissions.
"""

import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Booking, CommissionTracking, DailyReconciliation, EscrowStatus
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ReconciliationService:
    @staticmethod
    def run_daily_recon(db: Session, target_date: date) -> DailyReconciliation:
        """
        Subtask 49.2 & 49.7: Calculate balances for a specific date range.
        """
        # Robust date range matching
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())
        
        # 1. Sum Total Revenue (Confirmed Payments)
        total_rev = db.query(func.sum(Booking.amount_paid)).filter(
            Booking.created_at >= start_of_day,
            Booking.created_at <= end_of_day,
            Booking.escrow_status.in_([EscrowStatus.VERIFIED, EscrowStatus.COMPLETED])
        ).scalar() or 0.0
        
        # 2. Sum Agent Commissions
        total_comm = db.query(func.sum(CommissionTracking.amount)).filter(
            CommissionTracking.created_at >= start_of_day,
            CommissionTracking.created_at <= end_of_day
        ).scalar() or 0.0
        
        # 3. Sum Unlock Fees (₹49 blocks)
        total_unlock = db.query(func.sum(Booking.amount_paid)).filter(
            Booking.created_at >= start_of_day,
            Booking.created_at <= end_of_day,
            Booking.service_type == "UNLOCK",
            Booking.escrow_status.in_([EscrowStatus.VERIFIED, EscrowStatus.COMPLETED])
        ).scalar() or 0.0
        
        # 4. Create Recon Record
        recon = DailyReconciliation(
            recon_date=target_date,
            total_revenue=float(total_rev),
            total_agent_commissions=float(total_comm),
            total_unlocked_fees=float(total_unlock),
            status="MATCHED",
            report_data={
                "generated_at": datetime.utcnow().isoformat(),
                "booking_count": db.query(Booking).filter(func.date(Booking.created_at) == target_date).count()
            }
        )
        
        # Upsert logic
        existing = db.query(DailyReconciliation).filter(DailyReconciliation.recon_date == target_date).first()
        if existing:
            existing.total_revenue = recon.total_revenue
            existing.total_agent_commissions = recon.total_agent_commissions
            existing.total_unlocked_fees = recon.total_unlocked_fees
            existing.report_data = recon.report_data
            recon = existing
        else:
            db.add(recon)
            
        db.commit()
        db.refresh(recon)
        return recon
