from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional, cast
from datetime import datetime, date as date_type
import razorpay
import hmac
import hashlib
import json
import asyncio
import uuid

from database import get_db
from schemas import PaymentOrderSchema
from services.payment_service import PaymentService
from services.booking_service import BookingService
from services.unlock_service import UnlockService
from services.price_calculation_service import PriceCalculationService
from services.cache_service import cache_service
from services.route_verification_service import RouteVerificationService
from database.models import PrecalculatedRoute, User, Booking, Payment as PaymentModel, UnlockedRoute, CommissionTracking, PaymentSession, Refund as RefundModel
from api.dependencies import get_current_user, verify_webhook_signature
from utils.metrics import WEBHOOK_EVENTS_TOTAL, WEBHOOK_ERRORS_TOTAL
from utils.limiter import limiter

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# --- RAZORPAY STANDARD CHECKOUT RELATED ADMIN ENDPOINTS ---
@router.get("/refunds")
async def get_all_refunds(
    status_filter: Optional[str] = Query(None, description="Filter refunds by status (PENDING, PROCESSING, COMPLETED, FAILED, REJECTED)"),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Admin Only] Fetch all refund requests with filtering.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(RefundModel)
    if status_filter:
        query = query.filter(RefundModel.status == status_filter.upper())
    
    total = query.count()
    refunds = query.order_by(desc(RefundModel.created_at)).offset(skip).limit(limit).all()

    return {
        "success": True,
        "total": total,
        "skip": skip,
        "limit": limit,
        "refunds": [
            {
                "id": r.id,
                "payment_id": r.payment_id,
                "razorpay_refund_id": r.razorpay_refund_id,
                "amount": r.amount,
                "status": r.status,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "user_id": r.user_id,
                # "payment_method": PaymentModel.method # Method is on Payment, needs join
            } for r in refunds
        ]
    }

@router.post("/refunds/{refund_id}/approve")
async def approve_refund(
    refund_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Admin Only] Approve a refund request.
    Triggers Razorpay refund API call and updates internal status.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    refund = db.query(RefundModel).filter(RefundModel.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund request not found.")
    
    if refund.status not in ("PENDING", "PROCESSING"):
        raise HTTPException(status_code=400, detail=f"Refund is not in a modifiable state (current: {refund.status}).")

    payment = db.query(PaymentModel).filter(PaymentModel.id == refund.payment_id).first()
    if not payment or not payment.razorpay_payment_id:
        logger.warning(f"Attempted to approve refund {refund_id} for payment {payment.id} without Razorpay ID.")
        raise HTTPException(status_code=400, detail="Cannot approve refund: Payment is not Razorpay based or Razorpay ID missing.")

    try:
        payment_service = PaymentService(db=db) 
        refund_api_response = await payment_service.refund_payment(
            payment_id=payment.razorpay_payment_id,
            amount_rupees=refund.amount,
            reason=f"Admin approved refund (ID: {refund_id})",
            user_id=refund.user_id
        )
        
        if refund_api_response and refund_api_response.get("success"):
            refund.status = "PROCESSING" 
            refund.processed_at = datetime.utcnow()
            payment.refund_status = "PROCESSING" # Update payment's refund status too
            payment.refund_id = refund_api_response.get("refund_id") # Store Razorpay refund ID
            db.commit()
            db.refresh(refund)
            logger.info(f"Admin approved and initiated refund for refund ID: {refund_id}, Razorpay Refund ID: {refund.refund_id}")
            return {"success": True, "message": "Refund approved and initiated.", "status": refund.status}
        else:
            error_message = refund_api_response.get("error", "Refund initiation failed via Razorpay.")
            refund.status = "FAILED"
            refund.processed_at = datetime.utcnow()
            db.commit()
            logger.error(f"Admin approval failed to initiate Razorpay refund for {refund_id}: {error_message}")
            raise HTTPException(status_code=500, detail=error_message)

    except Exception as e:
        logger.error(f"Error during admin approval of refund {refund_id}: {e}", exc_info=True)
        refund.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during refund approval.")

@router.post("/refunds/{refund_id}/reject")
async def reject_refund(
    refund_id: str,
    reason: str = Query("No reason provided", description="Reason for rejecting the refund"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    [Admin Only] Reject a refund request.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    refund = db.query(RefundModel).filter(RefundModel.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund request not found.")
    
    if refund.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Refund is not in PENDING state (current: {refund.status}).")

    refund.status = "REJECTED"
    refund.reason = reason
    refund.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(refund)
    
    logger.info(f"Admin rejected refund request for ID: {refund_id} with reason: {reason}")
    
    # Optionally notify the user about rejection
    
    return {"success": True, "message": "Refund request rejected.", "status": refund.status}
