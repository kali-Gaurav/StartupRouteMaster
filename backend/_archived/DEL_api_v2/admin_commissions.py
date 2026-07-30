import logging
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, CommissionTracking, AgentWallet
from api.dependencies import require_role

logger = logging.getLogger("admin-commissions-api")
router = APIRouter(prefix="/admin/commissions", tags=["admin-commissions"])

@router.get("/summary", dependencies=[Depends(require_role(["admin"]))])
async def get_commission_summary(db: Session = Depends(get_db)):
    """
    [Task 44.8] Global Commission Stats.
    """
    total_pending = db.query(func.sum(CommissionTracking.amount)).filter(CommissionTracking.status == "PENDING").scalar() or 0.0
    total_settled = db.query(func.sum(CommissionTracking.amount)).filter(CommissionTracking.status == "SETTLED").scalar() or 0.0
    
    agent_count = db.query(User).filter(User.role == "agent").count()
    
    return {
        "total_unpaid_liability": total_pending,
        "total_paid_commissions": total_settled,
        "active_agent_count": agent_count,
        "escrow_health_score": 100 # TODO: Compare with actual balance
    }

@router.get("/top-earners", dependencies=[Depends(require_role(["admin"]))])
async def get_top_earners(db: Session = Depends(get_db)):
    """
    Returns top agents by total_earned.
    """
    top_wallets = db.query(AgentWallet).order_by(AgentWallet.total_earned.desc()).limit(10).all()
    
    return [
        {
            "user_id": w.user_id,
            "earned": w.total_earned,
            "pending": w.pending_commission,
            "last_payout": w.last_payout_at
        }
        for w in top_wallets
    ]
