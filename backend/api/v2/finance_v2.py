from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from database.config import get_db
from database.models import User, UnclaimedFund, Booking, FinancialLedger, EscrowStatus
from services.auth.jwt_handler import get_current_user
from services.finance.reconciliation_orchestrator import get_reconciliation_orchestrator
from services.finance.settlement_engine import get_settlement_engine
from sqlalchemy import func
from utils.responses import success_response, v3_response
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/finance/v2", tags=["Admin FinOps"])

def check_admin(user: User = Depends(get_current_user)):
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized: Admin access required.")
    return user

@router.get("/limbo-funds")
async def get_limbo_funds(db: Session = Depends(get_db), admin = Depends(check_admin)):
    """Lists all 'Limbo' payments waiting for manual reconciliation."""
    funds = db.query(UnclaimedFund).filter(UnclaimedFund.status == "PENDING").all()
    data = [{"id": f.id, "utr": f.utr_number, "amount": f.amount, "sender": f.sender_info, "created_at": f.created_at} for f in funds]
    return success_response(data=data)

@router.post("/limbo-funds/{fund_id}/claim")
async def claim_limbo_fund(
    fund_id: str,
    booking_id: str,
    db: Session = Depends(get_db),
    admin = Depends(check_admin)
):
    """Manually links an unclaimed fund to a specific booking."""
    fund = db.query(UnclaimedFund).filter(UnclaimedFund.id == fund_id).first()
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    
    if not fund or not booking:
        raise HTTPException(status_code=404, detail="Fund or Booking not found.")

    # 1. Update Fund Status
    fund.status = "CLAIMED"
    fund.claimed_by_user_id = admin.id
    fund.claim_metadata = {"booking_id": booking_id, "mode": "MANUAL_ADMIN"}
    
    # 2. Update Booking Status
    booking.update_escrow_status(db, EscrowStatus.VERIFIED, message="✅ Manually reconciled by Admin.", performed_by=admin.email)
    
    db.commit()
    logger.info(f"ADMIN_FINANCE_CLAIM | Fund:{fund_id} | Booking:{booking_id} | Admin:{admin.id}")
    return success_response(message=f"Fund {fund.utr_number} matched to Booking {booking.id}")

@router.post("/settlement/run")
async def trigger_settlement_run(db: Session = Depends(get_db), admin = Depends(check_admin)):
    """Triggers the batch settlement engine."""
    engine = get_settlement_engine(db)
    result = await engine.run_daily_settlement()
    logger.warning(f"ADMIN_FINANCE_SETTLEMENT_RUN | Admin:{admin.id}")
    return success_response(data=result)

@router.get("/ledger/summary")
async def get_ledger_summary(db: Session = Depends(get_db), admin = Depends(check_admin)):
    """Provides high-level account balances across the system."""
    debits = db.query(FinancialLedger.debit_account, func.sum(FinancialLedger.amount)).group_by(FinancialLedger.debit_account).all()
    credits = db.query(FinancialLedger.credit_account, func.sum(FinancialLedger.amount)).group_by(FinancialLedger.credit_account).all()
    
    data = {
        "accounts": {
            "debits": {acc: float(amt) for acc, amt in debits},
            "credits": {acc: float(amt) for acc, amt in credits}
        }
    }
    return success_response(data=data)
