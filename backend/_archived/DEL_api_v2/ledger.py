from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from database import get_db
from api.dependencies import get_current_user
from services.ledger_service import LedgerService
from database.models import User, Payment as PaymentModel, Refund, Booking

router = APIRouter(prefix="/v2/ledger", tags=["financial_ledger"])

@router.get("/stream")
async def get_user_ledger(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Task 12.1] Get Unified Financial Stream.
    Returns all payments and refunds in a chronological stream.
    """
    service = LedgerService(db)
    ledger = await service.get_user_ledger(str(current_user.id), limit=limit)

    return {
        "success": True,
        "user_id": str(current_user.id),
        "karma_balance": getattr(current_user, "karma_score", 0), # Fetch karma from user
        "ledger": ledger
    }

@router.get("/system_pnl")
async def get_system_pnl(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Admin Only] Real-time P&L analytics.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    service = LedgerService(db)
    return await service.get_system_pnl()

@router.get("/pnl")
async def get_profit_loss(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    [Admin Only] Real-time P&L analytics.
    """
    if user.role != "admin":
        return {"error": "Unauthorized"}
        
    service = LedgerService(db)
    return await service.get_system_pnl()
