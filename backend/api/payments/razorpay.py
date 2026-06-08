from typing import Dict, Optional
import logging
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.payment_service import PaymentService
from services.booking_service import BookingService
from database import get_db
from api.dependencies import get_current_user
from database.models import Booking, EscrowStatus

router = APIRouter(prefix="/razorpay", tags=["razorpay_standard"])
logger = logging.getLogger(__name__)

class RazorpayCreateOrderPayload(BaseModel):
    amount: int = Field(..., ge=100, description="Amount in paise. Minimum 100 paise.")
    currency: str = Field(default="INR", pattern=r"^INR$", description="Currency must be INR.")
    receipt: str = Field(..., min_length=1, description="Unique receipt identifier.")
    notes: Optional[Dict[str, str]] = Field(None, description="Optional metadata for this order.")


class RazorpayVerifyPaymentPayload(BaseModel):
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID.")
    razorpay_order_id: str = Field(..., description="Razorpay order ID.")
    razorpay_signature: str = Field(..., description="Signature returned by Razorpay.")
    payment_id: Optional[str] = Field(None, description="Optional internal payment record ID.")
    booking_id: Optional[str] = Field(None, description="Optional RouteMaster booking ID to update after verification.")


async def _complete_razorpay_agent_booking(booking_id: str) -> None:
    from database.session import SessionLocal
    from services.ws_manager import ws_manager

    await ws_manager.broadcast_log(booking_id, "Payment verified. Starting ticket fulfillment.", "BOOKING_INITIATED")
    with SessionLocal() as db:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return
        booking.escrow_status = EscrowStatus.BOOKING_INITIATED
        booking.escrow_message = "Payment verified. Ticket fulfillment is in progress."
        db.commit()


@router.post("/create-order")
async def create_razorpay_order(
    payload: RazorpayCreateOrderPayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Step 1: Create a Razorpay Order on the backend."""
    payment_service = PaymentService(db)
    if not payment_service.is_configured():
        logger.error("Razorpay attempted but not configured.")
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")

    logger.info(f"Creating Razorpay order for user {user.id}, amount: {payload.amount}")
    
    order_response = await payment_service.create_order(
        amount_rupees=payload.amount / 100.0,
        receipt_id=payload.receipt,
        customer_email=user.email,
        description=payload.notes.get("description") if payload.notes else "Standard Checkout",
        idempotency_key=payload.receipt,
        user_id=str(user.id)
    )

    if not order_response.get("success"):
        logger.error(f"Razorpay order creation failed: {order_response.get('error')}")
        raise HTTPException(status_code=500, detail=order_response.get("error", "Failed to create order."))

    return {
        "order_id": order_response["order_id"],
        "razorpay_order_id": order_response["order_id"],
        "amount": payload.amount,
        "currency": "INR",
        "key_id": payment_service.key_id,
    }


@router.post("/verify-payment")
async def verify_razorpay_payment(
    payload: RazorpayVerifyPaymentPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Step 3: Verify the payment signature on the backend."""
    payment_service = PaymentService(db)
    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment gateway not configured.")

    ip_address = request.client.host if request.client else None
    logger.info(f"Verifying Razorpay payment {payload.razorpay_payment_id} for user {user.id}")
    
    is_valid, error = payment_service.verify_payment(
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_signature=payload.razorpay_signature,
        ip_address=ip_address
    )

    if not is_valid:
        logger.warning(f"Payment verification failed for user {user.id}: {error}")
        raise HTTPException(status_code=400, detail=error or "Invalid payment signature.")

    if payload.booking_id:
        booking = db.query(Booking).filter(Booking.id == payload.booking_id, Booking.user_id == user.id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found.")

        if booking.escrow_status in {EscrowStatus.COMPLETED, EscrowStatus.BOOKING_INITIATED}:
            return {"success": True, "message": "Payment already verified for this booking."}

        if booking.service_type == "UNLOCK":
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.escrow_message = "Payment verified. Route details unlocked."
            booking.is_unlocked = True
        else:
            booking.escrow_status = EscrowStatus.VERIFIED
            booking.escrow_message = "Payment verified. Funds secured for ticket fulfillment."
            background_tasks.add_task(_complete_razorpay_agent_booking, str(booking.id))
        db.commit()
        logger.info("Razorpay payment linked to booking %s for user %s", booking.id, user.id)
        return {"success": True, "message": "Payment verified and booking updated."}

    # PATENT-LEVEL INTELLIGENCE: Handoff Trigger
    booking_service = BookingService(db)
    if payload.payment_id:
        try:
            booking_service.confirm_booking_payment(
                payload.razorpay_order_id,
                payload.razorpay_payment_id,
                "completed"
            )
            logger.info(f"🚀 AI Worker triggered for booking via Razorpay flow for order {payload.razorpay_order_id}")
        except Exception as e:
            logger.error(f"Failed to confirm booking after Razorpay payment: {e}")

    return {"success": True, "message": "Payment verified. AI Booking worker started."}
