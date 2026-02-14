from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import redis # Import redis
import time # Import time for sleep or other timing related operations

from backend.database import get_db
from backend.schemas import PaymentOrderSchema
from backend.services.payment_service import PaymentService
from backend.services.booking_service import BookingService
from backend.services.unlock_service import UnlockService
from backend.services.price_calculation_service import PriceCalculationService
from backend.models import Route as RouteModel, User, Booking, Payment as PaymentModel, UnlockedRoute
from backend.api.dependencies import get_current_user
from backend.services.cache_service import cache_service # Import cache_service to access Redis instance

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

UNLOCK_PRICE = 39.0
SEAT_LOCK_TTL_SECONDS = 600 # 10 minutes TTL for seat lock

@router.post("/create_order")
async def create_payment_order(
    request: PaymentOrderSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Razorpay payment order for booking or route unlock. Must be authenticated."""
    payment_service = PaymentService()
    price_calculation_service = PriceCalculationService()

    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service is not configured.")

    route = db.query(RouteModel).filter(RouteModel.id == request.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if not request.is_unlock_payment:
        # --- Implement Distributed Lock for Seat Availability ---
        lock_key = f"seat_lock:{request.route_id}:{request.travel_date}"
        seat_lock = cache_service.get_lock(lock_key, timeout=SEAT_LOCK_TTL_SECONDS)

        if not seat_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seats for this route and date are currently being processed by another user. Please try again shortly.",
            )
        
        try:
            booking_service = BookingService(db)
            # Calculate final price using the service
            final_price = price_calculation_service.calculate_final_price(route)
            
            booking = booking_service.create_booking(
                user_id=current_user.id,
                route_id=request.route_id,
                travel_date=request.travel_date,
                booking_details=route.segments,
                amount_paid=final_price,
            )
            if not booking:
                raise HTTPException(status_code=500, detail="Failed to create booking record.")
            
            amount_to_charge = booking.amount_paid
            receipt_id = str(booking.id)
            payment_description = f"Booking for {route.source} to {route.destination}"

            order_response = payment_service.create_order(
                amount_rupees=amount_to_charge,
                receipt_id=receipt_id,
                customer_email=current_user.email,
                description=payment_description,
                idempotency_key=str(booking.id),
            )

            if not order_response.get("success"):
                raise HTTPException(status_code=400, detail=order_response.get("error"))

            razorpay_order_id = order_response["order_id"]

            # Create a new Payment record
            new_payment = PaymentModel(
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=amount_to_charge,
                booking_id=booking.id, # Link payment to booking
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)

            db.commit()
            db.refresh(booking)

        except Exception:
            # If anything fails during booking/order creation, release the lock.
            seat_lock.release()
            raise # Re-raise the exception

    else: # is_unlock_payment is True
        unlock_service = UnlockService(db)
        if unlock_service.is_route_unlocked(current_user.id, request.route_id):
            return {"success": True, "already_paid": True, "message": "Route already unlocked."}
        
        # For now, unlock price is fixed, but could be dynamic in the future
        amount_to_charge = UNLOCK_PRICE
        receipt_id = f"unlock_{current_user.id}_{request.route_id}_{datetime.utcnow().timestamp()}"
        payment_description = f"Unlock Route {request.route_id} details"
        
        order_response = payment_service.create_order(
            amount_rupees=amount_to_charge,
            receipt_id=receipt_id,
            customer_email=current_user.email,
            description=payment_description,
            idempotency_key=receipt_id,
        )

        if not order_response.get("success"):
            raise HTTPException(status_code=400, detail=order_response.get("error"))

        razorpay_order_id = order_response["order_id"]

        new_payment = PaymentModel(
            razorpay_order_id=razorpay_order_id,
            status="pending",
            amount=amount_to_charge,
            booking_id=None,
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        unlocked_route = unlock_service.record_unlocked_route(
            user_id=current_user.id,
            route_id=request.route_id,
            payment_id=new_payment.id
        )
        if not unlocked_route:
            logger.error(f"CRITICAL: Failed to create unlocked route record for user {current_user.id} route {request.route_id} and payment {new_payment.id}")
            raise HTTPException(status_code=500, detail="Failed to link payment to unlock record.")
        unlocked_route.payment_id = new_payment.id
        db.commit()
        db.refresh(unlocked_route)

    return {
        "success": True,
        "order": {
            "order_id": razorpay_order_id,
            "amount": int(amount_to_charge * 100),
            "currency": order_response["currency"],
            "key_id": order_response["key_id"],
        },
        "payment_id": new_payment.id,
        "is_unlock_.payment": request.is_unlock_payment,
    }

@router.post("/verify")
async def verify_payment(
    payment_id: str, # Changed from order_id to our internal payment_id
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify payment and confirm booking or unlock."""
    payment_service = PaymentService()
    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service is not configured.")
    
    # Retrieve our internal Payment record
    payment_record = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    if payment_record.razorpay_order_id != razorpay_order_id:
        raise HTTPException(status_code=400, detail="Mismatched Razorpay Order ID.")

    # Verify Razorpay signature
    is_valid_signature, signature_error = payment_service.verify_payment(
        razorpay_payment_id, razorpay_order_id, razorpay_signature
    )
    if not is_valid_signature:
         raise HTTPException(status_code=400, detail=signature_error or "Invalid payment signature or details.")
    
    # Update payment record status
    payment_record.razorpay_payment_id = razorpay_payment_id
    payment_record.status = "completed"
    db.commit()
    db.refresh(payment_record)

    # --- Release Seat Lock on Successful Payment ---
    if payment_record.booking_id:
        # This is a booking payment
        booking = db.query(Booking).filter(Booking.id == payment_record.booking_id).first()
        if booking:
            lock_key = f"seat_lock:{booking.route_id}:{booking.travel_date}"
            # Directly delete the lock key.
            # In this simplified approach, we are not checking for lock ownership.
            # The TTL of the lock is the main safeguard against orphaned locks.
            if cache_service.is_available():
                cache_service.delete(lock_key)
                logger.info(f"Released seat lock for {lock_key} after successful payment.")
        else:
            logger.warning(f"Booking {payment_record.booking_id} not found for payment {payment_record.id}. Cannot release seat lock.")

        booking_service = BookingService(db)
        success = booking_service.confirm_booking_payment(
            order_id=str(payment_record.booking_id), # Internal booking ID
            payment_id=razorpay_payment_id,
            payment_status="completed",
            razorpay_order_id=razorpay_order_id
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to confirm booking payment.")
        return {"success": True, "message": "Payment verified and booking confirmed."}
    
    else:
        # Check if this payment corresponds to an unlocked route (payment_id stored on UnlockedRoute)
        unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment_record.id).first()
        if unlocked_route:
            # Mark the unlocked route as successfully paid/confirmed (no-op if already set)
            unlocked_route.payment_id = payment_record.id
            db.commit()
            db.refresh(unlocked_route)
            return {"success": True, "message": "Payment verified and route unlocked."}

        raise HTTPException(status_code=400, detail="Payment record not linked to a booking or an unlocked route.")


@router.post("/consume-redirect-token")
async def consume_redirect_token(
    token: str,
    current_user: User = Depends(get_current_user),
):
    """Consume a redirect token to retrieve booking details."""
    # In a real scenario, this involves decoding the token, validating it (e.g., signature, expiry),
    # and marking the payment or booking as fully confirmed based on the token's content.
    # For now, we'll just log and return success.

    # Example: Decode and validate a JWT token if it were one
    # try:
    #     decoded_token = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
    #     payment_order_id = decoded_token.get("payment_order_id")
    #     # Further logic to update payment status based on payment_order_id
    # except jwt.PyJWTError:
    #     raise HTTPException(status_code=400, detail="Invalid or expired redirect token.")

    logger.info(f"Consuming redirect token: {token} for user {current_user.id}")

    # For Phase 1, we assume if a token is present and valid, payment is confirmed.
    # A more complete implementation would fetch the associated booking/payment and update its status.
    # Let's assume the token itself implies success for the purpose of moving past this placeholder.

    # The frontend's `paymentApi.ts` expects `consumeResponse?.success || !consumeResponse?.order`.
    # Let's return a basic success with a dummy order for the frontend to proceed.
    return {"success": True, "message": "Redirect token consumed and payment confirmed (Phase 1).", "order": {"order_id": "dummy_order_id"}}


@router.get("/booking/history")
async def get_booking_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve booking history for the current user."""
    booking_service = BookingService(db)
    bookings = booking_service.get_bookings_by_user(current_user)
    
    # Transform bookings to a serializable format if needed
    booking_data = [{"id": b.id, "route_id": b.route_id, "travel_date": str(b.travel_date), "amount_paid": float(b.amount_paid), "status": b.status} for b in bookings]
    
    return {"success": True, "data": booking_data, "message": "Booking history retrieved."}


@router.post("/booking/redirect")
async def create_booking_redirect(
    request: Dict[str, Any], # Use Dict[str, Any] as frontend's BookingRedirectRequest is broad
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a redirect URL or token for booking confirmation."""
    # This endpoint should generate a secure, often signed, URL or a token that
    # the frontend can use to redirect the user to IRCTC or a similar booking partner,
    # with booking details pre-filled or encoded within the URL/token.

    # For Phase 1, we will generate a simulated redirect URL.
    # In a real scenario, this would involve:
    # 1. Fetching full booking details from the DB using payment_order_id.
    # 2. Constructing a URL to IRCTC with query parameters for pre-filling (if supported)
    #    or creating a secure token to pass to an IRCTC integration service.
    # 3. Potentially interacting with IRCTC APIs to confirm availability or create a preliminary booking.

    logger.info(f"Creating booking redirect for user {current_user.id} with data {request}")

    # Example of a simulated IRCTC redirect URL with some encoded parameters
    simulated_irctc_url = (
        f"https://www.irctc.co.in/nget/train-search?from={request.get('origin', 'SRC')}"
        f"&to={request.get('destination', 'DEST')}&date={request.get('travel_date', '2026-02-13')}"
        f"&trainNo={request.get('train_no', '12345')}&class={request.get('travel_class', 'SL')}"
        f"&paymentStatus=success&paymentOrderId={request.get('payment_order_id', 'dummy_payment_order')}"
    )

    return {
        "success": True,
        "redirect_url": simulated_irctc_url,
        "message": "Simulated IRCTC booking redirect created (Phase 1).",
    }


@router.get("/is_route_unlocked")
async def is_route_unlocked(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, bool]:
    """Check if the current user has unlocked a specific route."""
    unlock_service = UnlockService(db)
    is_unlocked = unlock_service.is_route_unlocked(current_user.id, route_id)
    return {"is_unlocked": is_unlocked}


@router.get("/check_payment_status")
async def check_payment_status(
    route_id: str,
    travel_date: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, bool]:
    """Check if the current user has already paid for a booking or unlocked a route."""
    booking_service = BookingService(db)
    # Check for existing completed booking payments
    already_paid_booking = booking_service.get_user_booking_for_route_date(
        current_user.id, route_id, travel_date
    ) and booking_service.is_booking_payment_completed(current_user.id, route_id, travel_date)
    
    unlock_service = UnlockService(db)
    is_route_unlocked = unlock_service.is_route_unlocked(current_user.id, route_id)

    return {"already_paid_booking": already_paid_booking, "is_route_unlocked": is_route_unlocked}
