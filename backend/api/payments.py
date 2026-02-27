from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date as date_type
import redis
import time
import json

from database import get_db
from schemas import PaymentOrderSchema
from services.payment_service import PaymentService
from services.booking_service import BookingService
from services.unlock_service import UnlockService
from services.price_calculation_service import PriceCalculationService
from services.cache_service import cache_service
from services.route_verification_service import RouteVerificationService
from database.models import Route as RouteModel, User, Booking, Payment as PaymentModel, UnlockedRoute, CommissionTracking
from api.dependencies import get_current_user, verify_webhook_signature
from services.redirect_service import redirect_service
from utils.metrics import WEBHOOK_EVENTS_TOTAL, WEBHOOK_ERRORS_TOTAL

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

UNLOCK_PRICE = 39.0
SEAT_LOCK_TTL_SECONDS = 600

@router.post("/create_order")
async def create_payment_order(
    request: PaymentOrderSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment_service = PaymentService()
    price_calculation_service = PriceCalculationService()
    unlock_service = UnlockService(db)

    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service is not configured.")

    route = db.query(RouteModel).filter(RouteModel.id == request.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Pre-payment verification for bookings
    if not request.is_unlock_payment:
        if not unlock_service.verify_live_availability(request.route_id, request.travel_date):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected route is no longer available. Please search again.")

        lock_key = f"seat_lock:{request.route_id}:{request.travel_date}"
        seat_lock = getattr(cache_service, "get_lock", lambda k, t: None)(lock_key, timeout=SEAT_LOCK_TTL_SECONDS)

        if seat_lock and not seat_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seats for this route and date are currently being processed.",
            )
        
        try:
            booking_service = BookingService(db)
            final_price = price_calculation_service.calculate_final_price(route)
            
            booking = booking_service.create_booking(
                user_id=current_user.id,
                route_id=request.route_id,
                travel_date=request.travel_date,
                booking_details=route.segments if hasattr(route, "segments") else {},
                amount_paid=final_price,
            )
            if not booking:
                raise HTTPException(status_code=500, detail="Failed to create booking record.")
            
            order_response = await payment_service.create_order(
                amount_rupees=booking.amount_paid,
                receipt_id=str(booking.id),
                customer_email=current_user.email,
                description=f"Booking for {route.source} to {route.destination}",
                idempotency_key=str(booking.id),
            )

            if not order_response.get("success"):
                raise HTTPException(status_code=400, detail=order_response.get("error"))

            razorpay_order_id = order_response["order_id"]
            new_payment = PaymentModel(
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=booking.amount_paid,
                booking_id=booking.id,
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)

            return {"success": True, "order": order_response, "payment_id": new_payment.id}

        except Exception as e:
            if seat_lock: seat_lock.release()
            logger.error(f"Error in create_payment_order for booking: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred.")
    else:
        # Handle Unlock Payment
        try:
            if await unlock_service.is_route_unlocked(current_user.id, request.route_id):
                 return {"success": True, "message": "Route already unlocked.", "unlocked": True}

            # NEW: Verify route before creating payment order
            verification_service = RouteVerificationService(db)
            verification_result = await verification_service.verify_route_for_unlock(
                route_id=request.route_id,
                travel_date=request.travel_date,
                train_number=request.train_number,
                from_station_code=request.from_station_code,
                to_station_code=request.to_station_code,
                source_station_name=request.source_station_name,
                destination_station_name=request.destination_station_name
            )
            
            # Log verification results
            logger.info(
                f"Route verification for unlock - Route: {request.route_id}, "
                f"API Calls: {verification_result.get('api_calls_made', 0)}, "
                f"Success: {verification_result.get('success', False)}"
            )
            
            # Log warnings if any
            if verification_result.get("warnings"):
                for warning in verification_result["warnings"]:
                    logger.warning(f"Route verification warning: {warning}")
            
            # If verification failed critically, still allow unlock but log error
            # (We don't block unlock if API fails - graceful degradation)
            if not verification_result.get("success") and verification_result.get("errors"):
                logger.error(
                    f"Route verification failed for {request.route_id}: "
                    f"{verification_result.get('errors')}"
                )
                # Continue anyway - database fallback will be used
            
            # Create payment order
            # Route model (gtfs_routes) doesn't have source/destination fields directly
            # Use verification result or route long_name
            route_source = verification_result.get("route_info", {}).get("from_station_name") or getattr(route, 'long_name', 'Unknown').split(' to ')[0] if hasattr(route, 'long_name') else "Unknown"
            route_dest = verification_result.get("route_info", {}).get("to_station_name") or getattr(route, 'long_name', 'Unknown').split(' to ')[-1] if hasattr(route, 'long_name') else "Unknown"
            
            order_response = await payment_service.create_order(
                amount_rupees=UNLOCK_PRICE,
                receipt_id=f"unlock_{request.route_id}_{current_user.id}",
                customer_email=current_user.email,
                description=f"Unlock Route {route_source} to {route_dest}",
                idempotency_key=f"unlock_{request.route_id}_{current_user.id}",
            )

            if not order_response.get("success"):
                raise HTTPException(status_code=400, detail=order_response.get("error"))

            razorpay_order_id = order_response["order_id"]
            new_payment = PaymentModel(
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=UNLOCK_PRICE,
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)
            
            # Link payment to unlock intent
            unlocked_route = UnlockedRoute(
                user_id=current_user.id,
                route_id=request.route_id,
                payment_id=new_payment.id,
                is_active=False # Becomes active after payment verification
            )
            db.add(unlocked_route)
            db.commit()

            return {
                "success": True,
                "order": order_response,
                "payment_id": new_payment.id,
                "verification": verification_result.get("verification", {}),
                "route_info": verification_result.get("route_info", {}),
                "warnings": verification_result.get("warnings", []),
                "api_calls_made": verification_result.get("api_calls_made", 0)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in create_payment_order for unlock: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.post("/verify")
async def verify_payment(
    payment_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment_service = PaymentService()
    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service not configured.")
    
    payment_record = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if payment_record.razorpay_order_id != razorpay_order_id:
        raise HTTPException(status_code=400, detail="Mismatched Razorpay Order ID.")

    is_valid, error = payment_service.verify_payment(
        razorpay_payment_id, razorpay_order_id, razorpay_signature
    )
    if not is_valid:
         raise HTTPException(status_code=400, detail=error or "Invalid payment signature.")
    
    payment_record.razorpay_payment_id = razorpay_payment_id
    payment_record.status = "completed"
    db.commit()
    db.refresh(payment_record)

    # if this payment corresponds to a booking, mark that booking confirmed
    if payment_record.booking_id:
        booking_service = BookingService(db)
        confirmed = booking_service.confirm_booking(payment_record.booking_id)
        if not confirmed:
            # log but still return success so frontend can handle upstream
            logger.warning(f"Payment succeeded but booking {payment_record.booking_id} could not be confirmed")
        return {"success": True, "message": "Payment verified and booking confirmed."}
    
    else:
        unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment_record.id).first()
        if unlocked_route:
            unlocked_route.is_active = True
            db.commit()
            return {"success": True, "message": "Payment verified and route unlocked."}

        raise HTTPException(status_code=400, detail="Payment not linked to any booking or unlock.")


# --- new endpoints added below ---

@router.get("/status/{razorpay_order_id}")
async def payment_status(
    razorpay_order_id: str,
    db: Session = Depends(get_db)
):
    """Return simple status of a payment by razorpay order id."""
    payment = db.query(PaymentModel).filter(PaymentModel.razorpay_order_id == razorpay_order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"order_id": razorpay_order_id, "status": payment.status}


@router.get("/booking/history")
async def payment_history(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated list of payments associated with the user (joins booking)."""
    query = db.query(PaymentModel).join(Booking, PaymentModel.booking_id == Booking.id)
    query = query.filter(Booking.user_id == current_user.id)
    total = query.count()
    payments = query.order_by(PaymentModel.created_at.desc()).offset(skip).limit(limit).all()
    # convert to serializable dicts
    result = []
    for p in payments:
        result.append({
            "id": p.id,
            "booking_id": p.booking_id,
            "razorpay_order_id": p.razorpay_order_id,
            "status": p.status,
            "amount": p.amount,
            "created_at": p.created_at.isoformat(),
        })
    return {"success": True, "total": total, "skip": skip, "limit": limit, "payments": result}

@router.get("/check_payment_status")
async def check_payment_status(
    route_id: str,
    travel_date: date_type,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check whether the user has already paid for a route/date combination."""
    # FastAPI will parse the incoming travel_date string into a date object.
    payment = (
        db.query(PaymentModel)
        .join(Booking, PaymentModel.booking_id == Booking.id)
        .filter(
            Booking.user_id == current_user.id,
            Booking.route_id == route_id,
            Booking.travel_date == travel_date,
        )
        .order_by(PaymentModel.created_at.desc())
        .first()
    )
    if not payment:
        return {"paid": False}
    return {"paid": payment.status == "completed", "already_paid_booking": bool(payment.booking_id)}


# ==================================================================
# Razorpay Webhook Handling
# ==================================================================
# This endpoint receives events from Razorpay (payments/refunds) and
# updates internal records accordingly. Signature verification is
# enforced via dependency to keep payloads secure.

@router.post("/webhook", dependencies=[Depends(verify_webhook_signature)])
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Razorpay webhook events to sync payment/refund status.

    Ensures idempotency by recording event IDs (or dedup keys) and ignoring duplicates.
    """
    payload = await request.json()
    event_id = payload.get("id")
    event_type = payload.get("event")

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})

    fallback_identifier = None
    fallback_status = None
    if event_type and event_type.startswith("payment."):
        fallback_identifier = payment_entity.get("order_id") or payment_entity.get("id")
        fallback_status = payment_entity.get("status")
    elif event_type and event_type.startswith("refund."):
        fallback_identifier = refund_entity.get("id")
        fallback_status = refund_entity.get("status")

    dedup_id = event_id or f"{event_type or 'unknown'}:{fallback_identifier or 'unknown'}:{fallback_status or 'unknown'}"

    from database.models import WebhookEvent

    existing = db.query(WebhookEvent).filter(WebhookEvent.id == dedup_id).first()
    if existing:
        logger.info(f"Webhook event {dedup_id} already processed, skipping.")
        return {"success": True, "message": "already processed"}

    new_evt = WebhookEvent(id=dedup_id, event_type=event_type or "unknown")
    db.add(new_evt)
    db.commit()

    # Payment events
    if event_type and event_type.startswith("payment."):
        r_payment_id = payment_entity.get("id")
        r_order_id = payment_entity.get("order_id")
        status = payment_entity.get("status")

        payment_record = None
        if r_payment_id:
            payment_record = (
                db.query(PaymentModel)
                .filter(PaymentModel.razorpay_payment_id == r_payment_id)
                .first()
            )
        if not payment_record and r_order_id:
            payment_record = (
                db.query(PaymentModel)
                .filter(PaymentModel.razorpay_order_id == r_order_id)
                .first()
            )
            if payment_record:
                # map Razorpay status to our internal status
                if status == "captured":
                    payment_record.status = "completed"
                elif status in ("failed", "cancelled"):
                    payment_record.status = "failed"
                else:
                    payment_record.status = status
                if r_payment_id:
                    payment_record.razorpay_payment_id = r_payment_id
                payment_record.razorpay_order_id = payment_record.razorpay_order_id or r_order_id
                db.commit()
                db.refresh(payment_record)

                # propagate to booking/unlock if needed
                if payment_record.booking_id and payment_record.status == "completed":
                    from services.booking_service import BookingService
                    booking_service = BookingService(db)
                    booking_service.confirm_booking(payment_record.booking_id)
                else:
                    unlocked_route = payment_record.unlocked_route
                    if unlocked_route and payment_record.status == "completed":
                        unlocked_route.is_active = True
                        db.commit()
    # Refund events
    if event_type and event_type.startswith("refund."):
        r_refund_id = refund_entity.get("id")
        status = refund_entity.get("status")
        if r_refund_id:
            from database.models import Refund as RefundModel
            refund_record = (
                db.query(RefundModel)
                .filter(RefundModel.razorpay_refund_id == r_refund_id)
                .first()
            )
            if refund_record:
                if status in ("processed", "completed", "paid"):
                    refund_record.status = "COMPLETED"
                elif status in ("failed", "cancelled"):
                    refund_record.status = "FAILED"
                else:
                    refund_record.status = status.upper()
                refund_record.processed_at = datetime.utcnow()
                db.commit()

    return {"success": True}
