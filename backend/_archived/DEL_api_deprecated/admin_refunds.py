from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
from typing import Optional
from pydantic import BaseModel

from database import get_db
from database.models import User
from api.dependencies import get_current_user
from services.refund_service import RefundService

router = APIRouter(prefix="/admin/refunds", tags=["admin_refunds"])
logger = logging.getLogger(__name__)

class RefundRequest(BaseModel):
    booking_id: str
    reason: str
    amount: float
    is_partial: bool = False
    cancellation_charge: float = 0.0

@router.post("/create")
async def create_refund(
    req: RefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin/Support endpoint to initiate a refund."""
    if current_user.role not in ["admin", "support"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    service = RefundService(db)
    result = service.create_refund_request(
        req.booking_id, req.reason, req.amount, req.is_partial, req.cancellation_charge
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/one_click_process/{booking_id}")
async def one_click_process_refund(
    booking_id: str,
    target_vpa: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 6.8: Customer support "One-Click Refund" button."""
    if current_user.role not in ["admin", "support"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    service = RefundService(db)
    result = service.process_refund(booking_id, target_vpa)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/approve/{booking_id}")
async def approve_high_value_refund(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 6.4: Manual approval workflow for high-value refunds."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required for high-value approvals")
        
    service = RefundService(db)
    result = service.admin_approve_refund(booking_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/bulk_process")
async def bulk_process_refunds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 6.7: Bulk refund processing via Bank API."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin authorization required")
        
    service = RefundService(db)
    result = service.process_bulk_refunds()
    return result
