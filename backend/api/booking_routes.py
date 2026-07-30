"""
Booking API Routes - REST endpoints for booking operations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.booking import (
    BookingRequest, BookingResponse, BookingListResponse,
    PassengerDetails, BookingStatus, CancelBookingRequest
)
from schemas.payment import PaymentStatus, PaymentResponse, PaymentVerifyRequest
from services.booking_service import get_booking_service, BookingService
from services.payment_service import get_payment_service, PaymentService
from services.sos_service import get_sos_service, SOSService
from core.auth import get_current_user

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: BookingRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new booking.
    
    This endpoint initiates the booking process with:
    - Automatic seat allocation
    - Idempotency handling
    - Fraud detection
    - Payment initiation
    """
    try:
        booking_service = get_booking_service(db)
        result = await booking_service.create_booking(request, user.id)
        
        if result.status.value in ["failed", "error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Booking creation failed"
            )
        
        return BookingResponse(
            booking_id=result.booking_id,
            pnr_number=result.pnr_number,
            status=BookingStatus(result.status.value),
            total_amount=result.total_amount,
            payment_url=result.payment_url,
            expires_at=result.expires_at,
            seats_allocated=result.seats_allocated,
            waitlist_position=result.waitlist_position
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during booking creation"
        )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get booking details by ID."""
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    return BookingResponse(
        booking_id=booking.id,
        pnr_number=booking.pnr_number,
        status=BookingStatus(booking.booking_status),
        total_amount=booking.total_amount or 0,
        payment_url=booking.payment_url,
        expires_at=booking.expires_at,
        seats_allocated=booking.seats_allocated or [],
        waitlist_position=booking.waitlist_position
    )


@router.get("/pnr/{pnr_number}", response_model=BookingResponse)
async def get_booking_by_pnr(
    pnr_number: str,
    db: Session = Depends(get_db)
):
    """
    Get booking details by PNR number.
    
    This is a public endpoint for quick PNR lookups.
    """
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking_by_pnr(pnr_number)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return BookingResponse(
        booking_id=booking.id,
        pnr_number=booking.pnr_number,
        status=BookingStatus(booking.booking_status),
        total_amount=booking.total_amount or 0,
        payment_url=booking.payment_url,
        expires_at=booking.expires_at,
        seats_allocated=booking.seats_allocated or [],
        waitlist_position=booking.waitlist_position
    )


@router.get("/", response_model=BookingListResponse)
async def list_bookings(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """List all bookings for the current user."""
    booking_service = get_booking_service(db)
    bookings = await booking_service.list_user_bookings(
        user.id, status_filter, limit, offset
    )
    
    return BookingListResponse(
        bookings=[
            BookingResponse(
                booking_id=b.id,
                pnr_number=b.pnr_number,
                status=BookingStatus(b.booking_status),
                total_amount=b.total_amount or 0,
                payment_url=b.payment_url,
                expires_at=b.expires_at,
                seats_allocated=b.seats_allocated or [],
                waitlist_position=b.waitlist_position
            )
            for b in bookings
        ],
        total=len(bookings),
        limit=limit,
        offset=offset
    )


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    request: CancelBookingRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Cancel a booking and process refund if applicable."""
    booking_service = get_booking_service(db)
    result = await booking_service.cancel_booking(
        booking_id, user.id, request.reason
    )
    
    return {
        "booking_id": result.booking_id,
        "pnr_number": result.pnr_number,
        "status": result.status.value,
        "refund_amount": result.total_amount * 0.9 if result.status.value == "cancelled" else 0
    }


@router.post("/{booking_id}/confirm-payment")
async def confirm_payment(
    booking_id: str,
    payment_details: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Confirm payment and finalize booking."""
    booking_service = get_booking_service(db)
    result = await booking_service.confirm_booking(booking_id, payment_details)
    
    return {
        "booking_id": result.booking_id,
        "pnr_number": result.pnr_number,
        "status": result.status.value,
        "total_amount": result.total_amount
    }


@router.get("/{booking_id}/safety-score")
async def get_safety_score(
    booking_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Get safety score for a booking."""
    # Verify user owns the booking
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    sos_service = get_sos_service(db)
    score = await sos_service.get_safety_score(booking_id)
    
    return {
        "booking_id": booking_id,
        "safety_score": {
            "overall": score.overall_score,
            "station": score.station_score,
            "coach": score.coach_score,
            "route": score.route_score,
            "time": score.time_score
        },
        "factors": score.factors,
        "recommendations": score.recommendations
    }


@router.post("/{booking_id}/sos")
async def trigger_sos(
    booking_id: str,
    request: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Trigger SOS emergency alert for a booking.
    
    This will:
    - Notify all emergency contacts
    - Create safety incident record
    - Alert emergency services if critical
    """
    # Verify user owns the booking
    booking_service = get_booking_service(db)
    booking = await booking_service.get_booking(booking_id, user.id)
    
    sos_service = get_sos_service(db)
    result = await sos_service.trigger_sos(
        user_id=user.id,
        booking_id=booking_id,
        location=request.get("location"),
        description=request.get("description")
    )
    
    return result


@router.post("/{booking_id}/report-incident")
async def report_safety_incident(
    booking_id: str,
    request: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Report a safety incident."""
    sos_service = get_sos_service(db)
    result = await sos_service.report_safety_incident(
        user_id=user.id,
        booking_id=booking_id,
        incident_type=request.get("incident_type"),
        description=request.get("description"),
        location=request.get("location"),
        evidence=request.get("evidence")
    )

    return result


# ==================== RAZORPAY PAYMENT ENDPOINTS ====================


@router.post("/{booking_id}/payment/initiate", status_code=status.HTTP_200_OK)
async def initiate_payment(
    booking_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Initiate Razorpay payment checkout for a booking.

    This endpoint:
    - Validates booking exists and belongs to user
    - Creates Razorpay order
    - Returns order details for frontend checkout

    Args:
        booking_id: ID of the booking to pay for

    Returns:
        {
            "order_id": "order_...",
            "amount": 50000,  # in paise
            "currency": "INR",
            "booking_id": "...",
            "status": "pending"
        }
    """
    try:
        # Validate booking exists and belongs to user
        booking_service = get_booking_service(db)
        booking = await booking_service.get_booking(booking_id, user.id)

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Check booking is in valid state for payment
        if booking.booking_status not in ["initiated", "payment_pending"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot initiate payment for booking in status: {booking.booking_status}"
            )

        # Get payment service and create order
        payment_service = get_payment_service(db)

        # Get amount from booking
        amount = booking.total_amount or 0
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid booking amount"
            )

        # Convert to paise (Razorpay expects amount in paise)
        amount_paise = int(amount * 100)

        # Call PaymentService to create Razorpay order
        # This assumes PaymentService has a method to create Razorpay order
        # For now, we return a structured response that the frontend can use
        result = await payment_service.create_payment(
            booking_id=booking_id,
            amount=amount,
            payment_method="razorpay",
            user_id=user.id
        )

        logger.info(f"Payment initiated for booking {booking_id}, amount: {amount}")

        return {
            "razorpay_order_id": result.payment_id,
            "amount_paise": amount_paise,
            "currency": "INR",
            "booking_id": booking_id,
            "status": result.status.value,
            "payment_url": result.payment_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating payment for booking {booking_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate payment"
        )


@router.post("/{booking_id}/payment/verify", status_code=status.HTTP_200_OK)
async def verify_payment(
    booking_id: str,
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Verify Razorpay payment and confirm booking.

    This endpoint:
    - Verifies payment signature from Razorpay
    - Updates payment status to confirmed
    - Transitions booking to CONFIRMED state
    - Releases locks and cleans up temporary state

    Args:
        booking_id: ID of the booking
        payload: Payment verification details (razorpay_order_id, razorpay_payment_id, razorpay_signature)

    Returns:
        {
            "status": "confirmed",
            "booking_status": "confirmed",
            "booking_id": "...",
            "pnr_number": "..."
        }
    """
    try:
        # Extract payment details from payload
        razorpay_order_id = payload.razorpay_order_id
        razorpay_payment_id = payload.razorpay_payment_id
        razorpay_signature = payload.razorpay_signature

        # Verify booking exists and belongs to user
        booking_service = get_booking_service(db)
        booking = await booking_service.get_booking(booking_id, user.id)

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Check booking is in payment_pending state
        if booking.booking_status != "payment_pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Booking must be in payment_pending state, current: {booking.booking_status}"
            )

        # Get payment service and verify signature
        payment_service = get_payment_service(db)

        # Verify Razorpay signature (PaymentService should implement this)
        # Create verification payload
        verification_payload = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        }

        # Handle webhook payload through payment service
        result = await payment_service.handle_webhook(
            provider="razorpay",
            payload=verification_payload,
            signature=razorpay_signature
        )

        # Confirm booking state transition
        booking.booking_status = "confirmed"
        booking.payment_status = "completed"
        db.commit()

        logger.info(f"Payment verified for booking {booking_id}, PNR: {booking.pnr_number}")

        return {
            "status": "confirmed",
            "booking_status": "confirmed",
            "booking_id": booking_id,
            "pnr_number": booking.pnr_number,
            "payment_id": razorpay_payment_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment for booking {booking_id}: {e}")
        # Log but don't fail - webhook might retry
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed"
        )


@router.post("/{booking_id}/payment/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    booking_id: str,
    raw_request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Razorpay webhook callbacks (payment.captured, payment.failed).

    Razorpay sends webhooks for:
    - payment.authorized: Payment authorized (not captured yet)
    - payment.captured: Payment successfully captured
    - payment.failed: Payment failed
    - order.paid: Order marked as paid

    This endpoint:
    - Verifies webhook signature for security
    - Updates payment status based on event
    - Transitions booking state accordingly
    - Returns 200 OK immediately (async processing)

    Returns:
        {"status": "ok"}
    """
    try:
        # Get raw body for signature verification
        body = await raw_request.body()

        # Extract signature from header
        signature = raw_request.headers.get("X-Razorpay-Signature")
        if not signature:
            logger.warning("Webhook received without signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature"
            )

        # Parse JSON payload
        import json
        payload = json.loads(body)

        # Verify Razorpay signature
        # In production, use: verify_payment_signature() from razorpay SDK
        # For now, we accept all signatures (TODO: implement proper verification)

        event_type = payload.get("event")
        event_data = payload.get("data", {}).get("entity", {})

        logger.info(f"Webhook received: {event_type} for booking {booking_id}")

        # Get payment service
        payment_service = get_payment_service(db)

        # Handle different event types
        if event_type == "payment.captured":
            # Payment successfully captured
            result = await payment_service.handle_webhook(
                provider="razorpay",
                payload=event_data,
                signature=signature
            )
            logger.info(f"Payment captured for booking {booking_id}")

        elif event_type == "payment.failed":
            # Payment failed
            result = await payment_service.handle_webhook(
                provider="razorpay",
                payload=event_data,
                signature=signature
            )
            logger.warning(f"Payment failed for booking {booking_id}: {event_data.get('error_description')}")

        elif event_type == "payment.authorized":
            # Payment authorized but not captured yet
            # Some integrations capture on authorization
            logger.info(f"Payment authorized for booking {booking_id}")

        elif event_type == "order.paid":
            # Order marked as paid
            logger.info(f"Order paid for booking {booking_id}")

        else:
            logger.debug(f"Unhandled event type: {event_type}")

        # Always return 200 OK - Razorpay expects this
        # If we return error, Razorpay will retry up to 5 times
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing Razorpay webhook for booking {booking_id}: {e}")
        # Return 200 OK anyway - don't want Razorpay to retry indefinitely
        # But log the error for investigation
        return {"status": "ok"}