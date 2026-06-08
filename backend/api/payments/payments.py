from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional, cast
from datetime import datetime, date as date_type
import redis
import time
import json
from pydantic import BaseModel

from database import get_db
from schemas import PaymentOrderSchema
from services.payment_service import PaymentService
from services.booking_service import BookingService
from services.unlock_service import UnlockService
from services.price_calculation_service import PriceCalculationService
from services.cache_service import cache_service
from services.route_verification_service import RouteVerificationService
from database.models import PrecalculatedRoute, User, Booking, Payment as PaymentModel, UnlockedRoute, CommissionTracking
from api.dependencies import get_current_user, verify_webhook_signature
from utils.metrics import WEBHOOK_EVENTS_TOTAL, WEBHOOK_ERRORS_TOTAL
from utils.limiter import limiter

router = APIRouter(prefix="/payment", tags=["payments"])
logger = logging.getLogger(__name__)

@router.get("/u/{short_id}")
async def redirect_upi(short_id: str):
    """
    Task 1.6: Short-URL redirector for UPI links.
    Redirects to the actual upi://pay URI.
    """
    from services.cache_service import cache_service
    from fastapi.responses import RedirectResponse
    
    upi_uri = cache_service.get(f"upi_short:{short_id}")
    if not upi_uri:
        raise HTTPException(status_code=404, detail="Payment link expired or invalid.")
    
    return RedirectResponse(url=upi_uri)

UNLOCK_PRICE = 39.0
SEAT_LOCK_TTL_SECONDS = 600

class VerifyPaymentPayload(BaseModel):
    payment_id: Optional[str] = None
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class BookingRedirectRequest(BaseModel):
    payment_order_id: str
    origin: str
    destination: str
    train_no: str
    travel_date: str
    travel_class: Optional[str] = None

class RedirectTokenPayload(BaseModel):
    token: str

@router.post("/unlock-route")
async def unlock_route_payment(
    request: Request,
    payload: PaymentOrderSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint for unlocking routes. Uses dynamic pricing based on complexity.
    """
    payment_service = PaymentService(db)
    unlock_service = UnlockService()
    price_calculation_service = PriceCalculationService()

    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service is not configured.")

    route = db.query(PrecalculatedRoute).filter(PrecalculatedRoute.id == payload.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # NEW: Verify route before creating payment order
    verification_service = RouteVerificationService()
    travel_date = payload.travel_date or datetime.now().strftime("%Y-%m-%d") # Fallback date

    verification_result = await verification_service.verify_route_for_unlock(
        route_id=payload.route_id,
        travel_date=travel_date,
        train_number=payload.train_number,
        from_station_code=payload.from_station_code,
        to_station_code=payload.to_station_code,
    )
    
    if not verification_result.get("success"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=verification_result.get("error", "Route verification failed."))

    # Log verification results
    logger.info(
        f"Route verification for unlock - Route: {payload.route_id}, "
        f"API Calls: {verification_result.get('api_calls_made', 0)}, "
        f"Success: {verification_result.get('success', False)}"
    )
    
    # Log warnings if any
    if verification_result.get("warnings"):
        for warning in verification_result["warnings"]:
            logger.warning(f"Route verification warning: {warning}")
    
    # If verification failed critically, still allow unlock but log error
    if not verification_result.get("success") and verification_result.get("errors"):
        logger.error(
            f"Route verification failed for {payload.route_id}: "
            f"{verification_result.get('errors')}"
        )
        # Continue anyway - database fallback will be used
    
    # Get dynamic fee
    route_complexity = verification_result.get("route_info", {}).get("complexity", 1.0) # Default complexity
    route_source = verification_result.get("route_info", {}).get("from_station_name") or getattr(route, "src", None) or (route.route_data.get("source") if isinstance(route.route_data, dict) else None) or "Unknown"
    route_dest = verification_result.get("route_info", {}).get("to_station_name") or getattr(route, "dest", None) or (route.route_data.get("destination") if isinstance(route.route_data, dict) else None) or "Unknown"
    
    total_fare = price_calculation_service.calculate_final_price(route)
    unlock_fee = await payment_service.calculate_unlock_fee(route_complexity, total_fare)

    order_response = await payment_service.create_order(
        amount_rupees=unlock_fee,
        receipt_id=f"unlock_{payload.route_id}_{current_user.id}",
        customer_email=current_user.email,
        description=f"Unlock Route {route_source} to {route_dest}",
        idempotency_key=f"unlock_{payload.route_id}_{current_user.id}",
        user_id=current_user.id,
    )

    if not order_response.get("success"):
        raise HTTPException(status_code=400, detail=order_response.get("error"))

    new_payment = PaymentModel(
        razorpay_order_id=order_response["order_id"],
        status="pending",
        amount=unlock_fee,
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    
    # Link payment to unlock intent
    unlocked_route = UnlockedRoute(
        user_id=current_user.id,
        route_id=payload.route_id,
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

@router.post("/create_order")
@limiter.limit("10/minute")
async def create_payment_order(
    request: Request,
    payload: PaymentOrderSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment_service = PaymentService(db)
    price_calculation_service = PriceCalculationService()
    unlock_service = UnlockService()

    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service is not configured.")

    route = db.query(PrecalculatedRoute).filter(PrecalculatedRoute.id == payload.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Pre-payment verification for bookings
    if not payload.is_unlock_payment:
        # TODO: Replace with a dedicated availability service if available.
        # For now, use route verification as the safety check before booking.
        verification_service = RouteVerificationService()
        verification_result = await verification_service.verify_route_for_unlock(
            route_id=payload.route_id,
            travel_date=payload.travel_date,
            train_number=payload.train_number,
            from_station_code=payload.from_station_code,
            to_station_code=payload.to_station_code,
        )

        if not verification_result.get("success"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected route is no longer available. Please search again.")

        lock_key = f"seat_lock:{payload.route_id}:{payload.travel_date}"
        get_lock = getattr(cache_service, "get_lock", None)
        seat_lock = cast(Any, get_lock(lock_key, timeout=SEAT_LOCK_TTL_SECONDS)) if callable(get_lock) else None

        if seat_lock and not seat_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seats for this route and date are currently being processed.",
            )
        
        booking = None
        try:
            booking_service = BookingService(db)
            final_price = price_calculation_service.calculate_final_price(route)
            
            booking_details = {}
            if isinstance(route.route_data, dict):
                booking_details = {
                    "segments": route.route_data.get("segments", []),
                    "source": route.route_data.get("source") or route.src,
                    "destination": route.route_data.get("destination") or route.dest,
                }
            else:
                booking_details = {
                    "segments": [],
                    "source": getattr(route, "src", "Unknown"),
                    "destination": getattr(route, "dest", "Unknown"),
                }

            booking = booking_service.create_booking(
                user_id=current_user.id,
                route_id=payload.route_id,
                travel_date=payload.travel_date,
                booking_details=booking_details,
                amount_paid=final_price,
            )
            if not booking:
                raise HTTPException(status_code=500, detail="Failed to create booking record.")
            
            route_source = booking_details.get("source") or getattr(route, "src", "Unknown")
            route_dest = booking_details.get("destination") or getattr(route, "dest", "Unknown")
            order_response = await payment_service.create_order(
                amount_rupees=booking.amount_paid,
                receipt_id=str(booking.id),
                customer_email=current_user.email,
                description=f"Booking for {route_source} to {route_dest}",
                idempotency_key=str(booking.id),
                user_id=current_user.id,
            )

            if not order_response.get("success"):
                raise HTTPException(status_code=400, detail=order_response.get("error"))

            razorpay_order_id = order_response["order_id"]
            new_payment = PaymentModel(
                user_id=current_user.id,
                route_id=payload.route_id,
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=booking.amount_paid,
                booking_id=booking.id,
                payment_method="RAZORPAY",
                payment_channel="RAZORPAY",
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)

            return {"success": True, "order": order_response, "payment_id": new_payment.id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in create_payment_order for booking: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred.")
        finally:
            if seat_lock:
                try:
                    seat_lock.release()
                except Exception:
                    pass
    else:
        # Handle Unlock Payment
        try:
            if unlock_service.is_route_unlocked(db, current_user.id, payload.route_id).is_unlocked:
                 return {"success": True, "message": "Route already unlocked.", "unlocked": True}

            # NEW: Verify route before creating payment order
            verification_service = RouteVerificationService()
            verification_result = await verification_service.verify_route_for_unlock(
                route_id=payload.route_id,
                travel_date=payload.travel_date,
                train_number=payload.train_number,
                from_station_code=payload.from_station_code,
                to_station_code=payload.to_station_code,
            )
            
            # Log verification results
            logger.info(
                f"Route verification for unlock - Route: {payload.route_id}, "
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
                    f"Route verification failed for {payload.route_id}: "
                    f"{verification_result.get('errors')}"
                )
                # Continue anyway - database fallback will be used
            
            # Create payment order
            # Route model (gtfs_routes) doesn't have source/destination fields directly
            # Use verification result or route long_name
            route_source = verification_result.get("route_info", {}).get("from_station_name")
            route_dest = verification_result.get("route_info", {}).get("to_station_name")
            if not route_source:
                route_source = getattr(route, "src", None) or (route.route_data.get("source") if isinstance(route.route_data, dict) else None) or "Unknown"
            if not route_dest:
                route_dest = getattr(route, "dest", None) or (route.route_data.get("destination") if isinstance(route.route_data, dict) else None) or "Unknown"
            
            order_response = await payment_service.create_order(
                amount_rupees=UNLOCK_PRICE,
                receipt_id=f"unlock_{payload.route_id}_{current_user.id}",
                customer_email=current_user.email,
                description=f"Unlock Route {route_source} to {route_dest}",
                idempotency_key=f"unlock_{payload.route_id}_{current_user.id}",
                user_id=current_user.id,
            )

            if not order_response.get("success"):
                raise HTTPException(status_code=400, detail=order_response.get("error"))

            razorpay_order_id = order_response["order_id"]
            new_payment = PaymentModel(
                user_id=current_user.id,
                route_id=payload.route_id,
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=UNLOCK_PRICE,
                payment_method="RAZORPAY",
                payment_channel="RAZORPAY",
            )
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)
            
            # Link payment to unlock intent
            unlocked_route = UnlockedRoute(
                user_id=current_user.id,
                route_id=payload.route_id,
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
@limiter.limit("10/minute")
async def verify_payment(
    request: Request,
    payload: VerifyPaymentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment_service = PaymentService(db)
    if not payment_service.is_configured():
        raise HTTPException(status_code=503, detail="Payment service not configured.")
    
    payment_record = None
    if payload.payment_id:
        payment_record = db.query(PaymentModel).filter(PaymentModel.id == payload.payment_id).first()
    if not payment_record:
        payment_record = db.query(PaymentModel).filter(PaymentModel.razorpay_order_id == payload.razorpay_order_id).first()

    if not payment_record:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if payment_record.razorpay_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Mismatched Razorpay Order ID.")
    if payment_record.user_id and payment_record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to verify this payment.")
    if not payment_record.user_id and payment_record.booking_id:
        booking = db.query(Booking).filter(Booking.id == payment_record.booking_id).first()
        if isinstance(booking, Booking):
            booking_user_id = booking.__dict__.get("user_id")
            if booking_user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to verify this payment.")

    is_valid, error = payment_service.verify_payment(
        payload.razorpay_payment_id,
        payload.razorpay_order_id,
        payload.razorpay_signature
    )
    if not is_valid:
         raise HTTPException(status_code=400, detail=error or "Invalid payment signature.")
    
    payment_record.razorpay_payment_id = payload.razorpay_payment_id
    payment_record.status = "completed"
    
    # [Task 1.1.4] Secondary Audit Reconciliation
    try:
        from database.models import PaymentTransaction
        transaction = PaymentTransaction(
            payment_id=payload.razorpay_payment_id,
            booking_id=payment_record.booking_id,
            amount=payment_record.amount,
            method=payment_record.payment_method or "RAZORPAY",
            status="success",
            provider_reference=payload.razorpay_payment_id
        )
        db.add(transaction)
    except Exception as te:
        logger.error(f"Failed to create reconciliation transaction: {te}")
        
    db.commit()
    db.refresh(payment_record)

    # if this payment corresponds to a booking, mark that booking confirmed
    if payment_record.booking_id:
        booking_service = BookingService(db)
        confirmed = booking_service.confirm_booking(payment_record.booking_id)
        if not confirmed:
            logger.warning(f"Payment succeeded but booking {payment_record.booking_id} could not be confirmed")
        return {"success": True, "message": "Payment verified and booking confirmed."}
    
    unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment_record.id).first()
    if unlocked_route:
        if unlocked_route.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to verify this payment.")
        unlocked_route.is_active = True
        db.commit()
        return {"success": True, "message": "Payment verified and route unlocked."}

    raise HTTPException(status_code=400, detail="Payment not linked to any booking or unlock.")


# --- new endpoints added below ---

@router.post("/create_order_v2")
async def create_payment_order_v2(
    request: PaymentOrderSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Optimized Payment Order creation.
    Supports UPI redirection for initial feedback month.
    """
    from services.unlock_service import UnlockService
    unlock_service = UnlockService()

    # 1. Verification Logic
    # In Phase 2, we perform live verification via RapidAPI before charging
    if request.is_unlock_payment:
        # Check if already unlocked
        if unlock_service.is_route_unlocked(db, current_user.id, request.route_id).is_unlocked:
             return {"success": True, "message": "Route already unlocked.", "unlocked": True}

        # 2. Dynamic VPA Merchant Load Balancer (Task 4)
        from services.merchant_vpa_service import merchant_vpa_service
        merchant_info = merchant_vpa_service.get_next_vpa()
        
        upi_id = merchant_info["vpa"]
        amount = UNLOCK_PRICE
        note = f"Unlock Route {request.route_id}"
        upi_link = f"upi://pay?pa={upi_id}&pn={merchant_info['name']}&am={amount}&cu=INR&tn={note}"

        # Create a pending payment record
        new_payment = PaymentModel(
            user_id=current_user.id,
            route_id=request.route_id,
            status="pending",
            amount=amount,
            payment_method="UPI",
            payment_channel="UPI",
            merchant_vpa=upi_id,
            razorpay_order_id=f"upi_{int(time.time())}_{current_user.id}"
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        # Link payment to unlock intent
        unlocked_route = UnlockedRoute(
            user_id=current_user.id,
            route_id=request.route_id,
            payment_id=new_payment.id,
            is_active=False
        )
        db.add(unlocked_route)
        db.commit()

        # For the feedback month, we also provide a 'bypass' link or just return the UPI intent
        return {
            "success": True,
            "payment_mode": "upi_intent",
            "upi_link": upi_link,
            "payment_id": new_payment.id,
            "message": "Please pay via UPI to unlock details. After payment, click 'I have paid'."
        }

    # Existing Razorpay logic fallback...
    return {"success": False, "message": "Manual booking logic used for feedback phase."}

@router.post("/manual_confirm_payment")
async def manual_confirm_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually confirm a payment during the initial feedback phase.
    User clicks 'I have paid' after UPI redirection.
    """
    payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.user_id and payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to confirm this payment.")
    payment.status = "completed"

    unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment.id).first()
    if unlocked_route:
        if unlocked_route.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to confirm this payment.")
        unlocked_route.is_active = True

    db.commit()
    return {"success": True, "message": "Route unlocked. You can now see full details."}

@router.get("/status/{razorpay_order_id}")
async def payment_status(
    razorpay_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return simple status of a payment by razorpay order id."""
    payment = db.query(PaymentModel).filter(PaymentModel.razorpay_order_id == razorpay_order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.user_id and payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this payment.")
    if not payment.user_id and payment.booking_id:
        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
        if isinstance(booking, Booking):
            booking_user_id = booking.__dict__.get("user_id")
            if booking_user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not authorized to view this payment.")
    return {"order_id": razorpay_order_id, "status": payment.status}


@router.get("/order_status/{razorpay_order_id}")
async def payment_order_status_alias(
    razorpay_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await payment_status(razorpay_order_id, db, current_user)


@router.post("/booking/redirect")
async def booking_redirect(
    payload: BookingRedirectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(PaymentModel).filter(PaymentModel.razorpay_order_id == payload.payment_order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if payment.user_id and payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this booking.")
    if payment.status != "completed":
        raise HTTPException(status_code=400, detail="Payment is not completed yet.")

    irctc_url = (
        f"https://www.irctc.co.in/nget/train-search?fromStation={payload.origin}"
        f"&toStation={payload.destination}&journeyDate={payload.travel_date}"
        f"&class={payload.travel_class or 'SL'}"
    )

    return {
        "success": True,
        "redirect_url": irctc_url,
        "irctc_url": irctc_url,
    }


@router.get("/unlocked-routes")
async def get_unlocked_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    routes = db.query(UnlockedRoute).filter(
        UnlockedRoute.user_id == str(current_user.id),
        UnlockedRoute.is_active == True
    ).all()
    return {
        "success": True,
        "routes": [route.route_id for route in routes if route.route_id],
    }


@router.post("/consume-redirect-token")
async def consume_redirect_token(
    payload: RedirectTokenPayload,
    current_user: User = Depends(get_current_user),
):
    if not payload.token or not isinstance(payload.token, str) or len(payload.token) < 8:
        raise HTTPException(status_code=400, detail="Invalid redirect token.")
    return {"success": True, "data": {"validated": True}}


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
                    unlocked_routes = payment_record.unlocked_route
                    if unlocked_routes and payment_record.status == "completed":
                        # If it's a list (default relationship without uselist=False), take the first
                        unlocked_route = unlocked_routes[0] if isinstance(unlocked_routes, list) else unlocked_routes
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

# ==========================================
# MVP PAYMENT SESSION / OTP SYSTEM
# ==========================================
import random
import string
from datetime import timedelta
from database.models import PaymentSession

class PaymentSessionRequest(BaseModel):
    journey_id: str
    amount: float = 39.0
    discount_code: Optional[str] = None
    user_region: str = "ALL" # New field for regional routing

class PaymentSessionVerify(BaseModel):
    session_code: str
    journey_id: str

@router.post("/create_session")
async def create_payment_session(
    request: PaymentSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a simple payment session for UPI.
    NEW: Performs real-time verification of ALL segments before allowing session creation.
    Task 5: Now includes Platform Fee & GST breakdown.
    """
    # 1. Real-time Verification (Phase 10 Core Requirement)
    verification_service = RouteVerificationService()
    # Note: we use tomorrow's date if not specified, but usually search context provides it
    travel_date = datetime.now().strftime("%Y-%m-%d") # Fallback
    
    logger.info(f"Triggering pre-payment verification for route {request.journey_id}")
    verify_result = await verification_service.verify_route_for_unlock(
        route_id=request.journey_id,
        travel_date=travel_date
    )
    
    if not verify_result.get("success"):
        raise HTTPException(status_code=400, detail=verify_result.get("error", "Route verification failed"))

    # 2. Task 5: Platform Fee & GST Calculation
    from services.tax_engine_service import tax_engine
    # Use request.amount as base fare if provided, otherwise default to 39.0
    breakdown = tax_engine.calculate_breakdown(request.amount, request.discount_code)
    final_amount = breakdown["total"]

    # Generate random 6-character session code
    session_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Task 4: Dynamic VPA Merchant Load Balancer (with Region support)
    from services.merchant_vpa_service import merchant_vpa_service
    merchant_info = merchant_vpa_service.get_next_vpa()
    
    # Store in DB with verification snapshot and fee breakdown
    session = PaymentSession(
        user_id=str(current_user.id),
        route_id=request.journey_id,
        session_code=session_code,
        amount=final_amount,
        verification_details={
            "verification": verify_result,
            "breakdown": breakdown
        },
        expires_at=datetime.utcnow() + timedelta(minutes=10) # Task 10: Strict 10 min
    )
    db.add(session)
    db.commit()
    
    # Task 7.5 & 7.10: Initialize Session Lock
    from services.session_lock_service import session_lock_service
    lock_service = session_lock_service
    # Using journey_id as booking_id placeholder since they map 1:1 in this context
    await lock_service.initialize_lock(session_code, str(current_user.id), booking_id=request.journey_id)
    
    # Generate UPI intent with load-balanced VPA and total amount
    from utils.payments import generate_upi_uri
    upi_link, tid = generate_upi_uri(
        merchant_vpa=merchant_info["vpa"],
        merchant_name=merchant_info["name"],
        amount=final_amount,
        transaction_note=f"Unlock_{session_code}"
    )
    
    # Record volume in tracker (Task 4)
    merchant_vpa_service.record_volume(merchant_info["vpa"], final_amount)
    
    return {
        "success": True,
        "session_code": session_code,
        "upi_link": upi_link,
        "amount_breakdown": breakdown,
        "merchant_name": merchant_info["name"],
        "verification": verify_result, # Frontend shows 'Verified' badge
        "message": f"Route verified. Please pay {final_amount} to {merchant_info['name']} and enter the code to unlock.",
        "expires_at": session.expires_at.isoformat() if session.expires_at else None
    }

@router.post("/refresh_session/{old_session_code}")
async def refresh_payment_session(
    old_session_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Task 10.3: "Refresh QR" button for expired sessions.
    Generates a new session code and 10-minute window for an expired session.
    """
    old_session = db.query(PaymentSession).filter(
        PaymentSession.session_code == old_session_code,
        PaymentSession.user_id == str(current_user.id)
    ).first()
    
    if not old_session:
        raise HTTPException(status_code=404, detail="Original session not found")
        
    if old_session.status == "VERIFIED":
        raise HTTPException(status_code=400, detail="Cannot refresh a verified session")
        
    # Mark old as explicitly expired if it isn't already
    old_session.status = "EXPIRED"
    
    # Generate new random 6-character session code
    new_session_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Create new session based on old data
    new_session = PaymentSession(
        user_id=str(current_user.id),
        route_id=old_session.route_id,
        session_code=new_session_code,
        amount=old_session.amount,
        verification_details=old_session.verification_details,
        expires_at=datetime.utcnow() + timedelta(minutes=10) # Fresh 10 min window
    )
    db.add(new_session)
    db.commit()
    
    # Initialize lock for new session
    from services.session_lock_service import session_lock_service
    lock_service = session_lock_service
    await lock_service.initialize_lock(new_session_code, str(current_user.id), booking_id=old_session.route_id)
    
    # Generate new UPI intent
    from services.merchant_vpa_service import merchant_vpa_service
    merchant_info = merchant_vpa_service.get_next_vpa()
    from utils.payments import generate_upi_uri
    upi_link, tid = generate_upi_uri(
        merchant_vpa=merchant_info["vpa"],
        merchant_name=merchant_info["name"],
        amount=new_session.amount,
        transaction_note=f"Unlock_{new_session_code}"
    )
    
    return {
        "success": True,
        "session_code": new_session_code,
        "upi_link": upi_link,
        "merchant_name": merchant_info["name"],
        "expires_at": new_session.expires_at.isoformat() if new_session.expires_at else None,
        "message": "Session refreshed successfully."
    }

@router.post("/heartbeat/{session_code}")
async def payment_heartbeat(
    session_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Task 7.10: Heartbeat check.
    Frontend calls this every 30s while on the payment page.
    """
    from services.session_lock_service import session_lock_service
    lock_service = session_lock_service

    is_active = await lock_service.record_heartbeat(session_code)
    if not is_active:
        raise HTTPException(status_code=400, detail="Session expired or invalid")
        
    return {"success": True, "status": "ACTIVE"}

@router.get("/admin/vpa_dashboard")
async def admin_vpa_dashboard(current_user: User = Depends(get_current_user)):
    """
    Task 4.7: Real-time VPA utilization dashboard endpoint.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    from services.merchant_vpa_service import merchant_vpa_service
    return {
        "success": True,
        "stats": merchant_vpa_service.get_dashboard_stats()
    }

@router.get("/admin/export_gstr1")
async def export_gstr1(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 5.5: Monthly GSTR-1 export utility."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
        
    from services.tax_engine_service import tax_engine
    from fastapi.responses import PlainTextResponse
    
    csv_data = tax_engine.export_gstr1_csv(db, month, year)
    
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gstr1_{year}_{month}.csv"}
    )

@router.get("/invoice/{payment_id}/pdf")
async def download_invoice_pdf(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Task 5.4: Tax Invoice generator (PDF) for the user."""
    payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    # Security: Only admin or the owner can download
    unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment.id).first()
    if not unlocked_route or (unlocked_route.user_id != str(current_user.id) and current_user.role != "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    from services.tax_engine_service import tax_engine
    from fastapi.responses import StreamingResponse
    
    # Calculate breakdown
    base_fare = payment.amount - 39.0 # Placeholder logic for demo
    if base_fare < 0: base_fare = payment.amount
    
    breakdown = tax_engine.calculate_breakdown(base_fare)
    
    pdf_buffer = tax_engine.generate_tax_invoice_pdf(
        transaction_id=str(payment.razorpay_order_id or payment.id),
        date_str=payment.created_at.strftime("%Y-%m-%d"),
        breakdown=breakdown
    )
    
    if not pdf_buffer:
        raise HTTPException(status_code=500, detail="PDF generation failed (ReportLab missing?)")
        
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{payment_id}.pdf"}
    )

class ClickAnalyticsRequest(BaseModel):
    session_code: str
    selected_app: str # 'gpay', 'phonepe', 'paytm', 'qr_fallback', 'copy_vpa'
    device_os: str # 'ios', 'android', 'web'

@router.get("/intents/{session_code}")
async def get_payment_intents(
    session_code: str,
    db: Session = Depends(get_db)
):
    """
    Task 9.3 & 9.8: Mobile Deep-Link Intent Generator.
    Returns app-specific intent URIs for the frontend.
    """
    session = db.query(PaymentSession).filter(PaymentSession.session_code == session_code).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Reconstruct the base URI (In prod, we'd store the merchant VPA used in the session)
    # Defaulting to our North node for demo
    vpa = "gauravnagar@okaxis" 
    name = "RouteMaster"
    amount = session.amount
    
    base_upi = f"upi://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tn=Unlock_{session_code}"
    
    # Android Intent formats
    intents = {
        "generic": base_upi,
        "gpay": f"intent://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tn=Unlock_{session_code}#Intent;scheme=upi;package=com.google.android.apps.nbu.paisa.user;end",
        "phonepe": f"intent://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tn=Unlock_{session_code}#Intent;scheme=upi;package=com.phonepe.app;end",
        "paytm": f"intent://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tn=Unlock_{session_code}#Intent;scheme=upi;package=net.one97.paytm;end",
        "bhim": f"intent://pay?pa={vpa}&pn={name}&am={amount}&cu=INR&tn=Unlock_{session_code}#Intent;scheme=upi;package=in.org.npci.upiapp;end"
    }
    
    return {"success": True, "intents": intents}

@router.post("/analytics/click")
async def track_app_click(
    request: ClickAnalyticsRequest,
    db: Session = Depends(get_db)
):
    """
    Task 9.7: Track "App Click-through Rate".
    Allows the frontend to prioritize sorting based on historical usage (Task 9.2).
    """
    # Store analytics in Redis for fast aggregation
    from services.cache_service import cache_service
    
    # Increment global counter for the app
    if cache_service.redis:
        cache_service.redis.hincrby("payment_app_analytics", request.selected_app, 1)
    
    # Log it for potential audit
    logger.info(f"Payment Click Analytics - Session: {request.session_code}, App: {request.selected_app}, OS: {request.device_os}")
    
    return {"success": True}

@router.post("/confirm_manual")
async def confirm_payment_session(
    request_data: PaymentSessionVerify,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verifies the payment session code entered by the user.
    """
    # 1. Check Fraud Lockout (Task 3)
    from services.fraud_detection_service import fraud_service
    client_ip = request.client.host if request.client else None
    device_fp = request.headers.get("X-Device-Fingerprint") # Task 3.3
    
    is_valid, error = fraud_service.validate_utr_advanced(
        db,
        request_data.session_code,
        str(current_user.id),
        ip_address=client_ip,
        device_fp=device_fp
    )
    
    if not is_valid:
        raise HTTPException(status_code=403, detail=error)

    session = db.query(PaymentSession).filter(
        PaymentSession.session_code == request_data.session_code,
        PaymentSession.route_id == request_data.journey_id,
        PaymentSession.user_id == current_user.id
    ).first()
    
    if not session:
        # Record failed attempt for fraud detection
        fraud_service.record_attempt(str(current_user.id), False)
        if client_ip: fraud_service.record_attempt(f"IP:{client_ip}", False)
        if device_fp: fraud_service.record_attempt(f"FP:{device_fp}", False)
        raise HTTPException(status_code=400, detail="Invalid session code or journey ID.")
        
    if session.status == "VERIFIED":
        fraud_service.record_attempt(str(current_user.id), True)
        return {"success": True, "message": "Already verified"}
        
    if not session.expires_at or session.expires_at < datetime.utcnow():
        session.status = "EXPIRED"
        db.commit()
        fraud_service.record_attempt(str(current_user.id), False)
        raise HTTPException(status_code=400, detail="Session code expired.")
        
    # Mark as verified
    session.status = "VERIFIED"
    fraud_service.record_attempt(str(current_user.id), True)
    if client_ip: fraud_service.record_attempt(f"IP:{client_ip}", True)
    
    new_payment = PaymentModel(
        status="completed",
        amount=session.amount,
        razorpay_order_id=f"manual_{session.session_code}",
        razorpay_payment_id=f"pay_{session.session_code}",
        created_at=datetime.utcnow()
    )
    db.add(new_payment)
    db.flush()
    
    from database.models import PrecalculatedRoute
    route_exists = db.query(PrecalculatedRoute).filter(PrecalculatedRoute.id == request_data.journey_id).first()
    
    unlocked_route = UnlockedRoute(
        user_id=str(current_user.id),
        route_id=request_data.journey_id if route_exists else None,
        cached_route_id=request_data.journey_id if not route_exists else None,
        is_active=True,
        payment_id=new_payment.id
    )

    db.add(unlocked_route)
    db.commit()
    db.refresh(unlocked_route)
    logger.info(f"DEBUG: Manually unlocked route {request_data.journey_id} for user {current_user.id}. ID in DB: {unlocked_route.id}")
    
    return {
        "success": True, 
        "message": "Payment confirmed and route unlocked."
    }

    return {"success": True, "message": f"Lockout cleared for {identifier}"}

@router.post("/refund/{payment_id}")
async def request_refund(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initiate a refund for a given payment.
    """
    payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")
        
    # Security: Only admin or the owner can request refund
    if payment.user_id != str(current_user.id) and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to request refund.")
        
    if payment.status == "completed" and not payment.razorpay_payment_id:
        # If it was a manual UPI payment and it's completed, we need a way to track refunds.
        # For now, we simulate and update the status.
        payment.status = "refund_requested"
        db.commit()
        db.refresh(payment)
        
        # Here, we would trigger a background job to notify Razorpay/Bank.
        # For now, just update status and log.
        logger.info(f"Manual refund requested for payment ID: {payment.id}")
        return {"success": True, "message": "Refund request processed.", "status": payment.status}

    if not payment.razorpay_payment_id:
        raise HTTPException(status_code=400, detail="Refund can only be initiated for Razorpay payments.")
    
    if payment.refund_status not in ("NOT_APPLICABLE", "FAILED"):
        raise HTTPException(status_code=400, detail=f"Refund already processed or pending. Current status: {payment.refund_status}")

    payment_service = PaymentService(db) # Assuming PaymentService needs db instance
    try:
        refund_success, refund_error, refund_data = await payment_service.refund_payment(
            payment_id=payment.razorpay_payment_id,
            amount_rupees=payment.amount,
            reason="User requested refund",
            user_id=str(current_user.id)
        )
        
        if refund_success:
            payment.refund_status = "processing"
            payment.refund_id = refund_data.get("id") if refund_data else None
            payment.refund_amount = payment.amount
            db.commit()
            db.refresh(payment)
            return {"success": True, "message": "Refund initiated successfully.", "status": payment.refund_status, "refund_id": payment.refund_id}
        else:
            error_message = refund_error or "Refund failed for unknown reasons."
            payment.refund_status = "failed"
            db.commit()
            logger.error(f"Razorpay refund initiation failed for payment {payment.id}: {error_message}")
            raise HTTPException(status_code=500, detail=error_message)
            
    except Exception as e:
        logger.error(f"Error initiating refund for payment {payment.id}: {e}")
        payment.refund_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail="Internal server error during refund initiation.")


