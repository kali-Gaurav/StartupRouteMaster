from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import redis
import time
import json

from backend.database import get_db
from backend.schemas import PaymentOrderSchema
from backend.services.payment_service import PaymentService
from backend.services.booking_service import BookingService
from backend.services.unlock_service import UnlockService
from backend.services.price_calculation_service import PriceCalculationService
from backend.services.cache_service import cache_service
from backend.models import Route as RouteModel, User, Booking, Payment as PaymentModel, UnlockedRoute, CommissionTracking
from backend.api.dependencies import get_current_user, verify_webhook_signature
from backend.services.redirect_service import redirect_service
from backend.utils.metrics import WEBHOOK_EVENTS_TOTAL, WEBHOOK_ERRORS_TOTAL # New: Import custom metrics

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
        seat_lock = cache_service.get_lock(lock_key, timeout=SEAT_LOCK_TTL_SECONDS)

        if not seat_lock.acquire(blocking=False):
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
                booking_details=route.segments,
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

        except Exception as e:
            seat_lock.release()
            logger.error(f"Error in create_payment_order for booking: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred.")
    else:
        if unlock_service.is_route_unlocked(current_user.id, request.route_id):
            return {"success": True, "already_paid": True, "message": "Route already unlocked."}
        
        amount_to_charge = UNLOCK_PRICE
        receipt_id = f"unlock_{current_user.id}_{request.route_id}_{datetime.utcnow().timestamp()}"
        
        order_response = await payment_service.create_order(
            amount_rupees=amount_to_charge,
            receipt_id=receipt_id,
            customer_email=current_user.email,
            description=f"Unlock Route {request.route_id} details",
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
            raise HTTPException(status_code=500, detail="Failed to link payment to unlock record.")
    
    return {
        "success": True,
        "order": {
            "order_id": razorpay_order_id,
            "amount": int(order_response["amount"] * 100),
            "currency": order_response["currency"],
            "key_id": order_response["key_id"],
        },
        "payment_id": new_payment.id,
        "is_unlock_payment": request.is_unlock_payment,
    }

@router.post("/webhook", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_webhook_signature)])
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    provider_name = "razorpay" # Assuming Razorpay for this webhook
    event_type = "unknown"
    
    # Increment total events received
    WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type="received", status="processing").inc()

    try:
        payload_raw = await request.body()
        payload = json.loads(payload_raw)
        event = payload.get("event")
        event_type = event # Update event_type label if available
        logger.info(f"Received Razorpay webhook event: {event}")

        if event == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            payment_status = payment_entity.get("status")

            if not all([order_id, payment_id, payment_status]):
                logger.error("Webhook payload missing required fields.")
                WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="missing_fields").inc()
                WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
                return {"status": "error", "message": "Missing fields."}

            booking_service = BookingService(db)
            if not await booking_service.confirm_booking_payment(order_id, payment_id, payment_status):
                logger.error(f"Failed to process webhook for order {order_id}")
                WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="processing_failed").inc()
                WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
                return {"status": "error", "message": "Failed to process payment confirmation."}
        
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="success").inc()
        return {"status": "ok"}
    except json.JSONDecodeError:
        logger.error("Webhook payload is not valid JSON.")
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="invalid_json").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except HTTPException as e:
        # Re-raise HTTP exceptions from dependencies (like invalid signature)
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="http_exception").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred during webhook processing: {e}", exc_info=True)
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="unexpected_error").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during webhook processing.")


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

    if payment_record.booking_id:
        booking = db.query(Booking).filter(Booking.id == payment_record.booking_id).first()
        if booking:
            lock_key = f"seat_lock:{booking.route_id}:{booking.travel_date}"
            if cache_service.is_available():
                cache_service.delete(lock_key)
        
        booking_service = BookingService(db)
        if not await booking_service.confirm_booking_payment(
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            payment_status="completed",
        ):
            raise HTTPException(status_code=500, detail="Failed to confirm booking payment.")
        return {"success": True, "message": "Payment verified and booking confirmed."}
    
    else:
        unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment_record.id).first()
        if unlocked_route:
            return {"success": True, "message": "Payment verified and route unlocked."}

        raise HTTPException(status_code=400, detail="Payment not linked to any booking or unlock.")


from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date as date_type
import redis
import time
import json

from backend.database import get_db
from backend.schemas import PaymentOrderSchema
from backend.services.payment_service import PaymentService
from backend.services.booking_service import BookingService
from backend.services.unlock_service import UnlockService
from backend.services.price_calculation_service import PriceCalculationService
from backend.services.cache_service import cache_service
from backend.models import Route as RouteModel, User, Booking, Payment as PaymentModel, UnlockedRoute, CommissionTracking
from backend.api.dependencies import get_current_user, verify_webhook_signature
from backend.services.redirect_service import redirect_service
from backend.utils.metrics import WEBHOOK_EVENTS_TOTAL, WEBHOOK_ERRORS_TOTAL # New: Import custom metrics

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
        seat_lock = cache_service.get_lock(lock_key, timeout=SEAT_LOCK_TTL_SECONDS)

        if not seat_lock.acquire(blocking=False):
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
                booking_details=route.segments,
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

        except Exception as e:
            seat_lock.release()
            logger.error(f"Error in create_payment_order for booking: {e}")
            raise HTTPException(status_code=500, detail="An internal error occurred.")
    else:
        if unlock_service.is_route_unlocked(current_user.id, request.route_id):
            return {"success": True, "already_paid": True, "message": "Route already unlocked."}
        
        amount_to_charge = UNLOCK_PRICE
        receipt_id = f"unlock_{current_user.id}_{request.route_id}_{datetime.utcnow().timestamp()}"
        
        order_response = await payment_service.create_order(
            amount_rupees=amount_to_charge,
            receipt_id=receipt_id,
            customer_email=current_user.email,
            description=f"Unlock Route {request.route_id} details",
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
            raise HTTPException(status_code=500, detail="Failed to link payment to unlock record.")
    
    return {
        "success": True,
        "order": {
            "order_id": razorpay_order_id,
            "amount": int(order_response["amount"] * 100),
            "currency": order_response["currency"],
            "key_id": order_response["key_id"],
        },
        "payment_id": new_payment.id,
        "is_unlock_payment": request.is_unlock_payment,
    }

@router.post("/webhook", status_code=status.HTTP_200_OK, dependencies=[Depends(verify_webhook_signature)])
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    provider_name = "razorpay" # Assuming Razorpay for this webhook
    event_type = "unknown"
    
    # Increment total events received
    WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type="received", status="processing").inc()

    try:
        payload_raw = await request.body()
        payload = json.loads(payload_raw)
        event = payload.get("event")
        event_type = event # Update event_type label if available
        logger.info(f"Received Razorpay webhook event: {event}")

        if event == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            payment_status = payment_entity.get("status")

            if not all([order_id, payment_id, payment_status]):
                logger.error("Webhook payload missing required fields.")
                WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="missing_fields").inc()
                WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
                return {"status": "error", "message": "Missing fields."}

            booking_service = BookingService(db)
            if not await booking_service.confirm_booking_payment(order_id, payment_id, payment_status):
                logger.error(f"Failed to process webhook for order {order_id}")
                WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="processing_failed").inc()
                WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
                return {"status": "error", "message": "Failed to process payment confirmation."}
        
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="success").inc()
        return {"status": "ok"}
    except json.JSONDecodeError:
        logger.error("Webhook payload is not valid JSON.")
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="invalid_json").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except HTTPException as e:
        # Re-raise HTTP exceptions from dependencies (like invalid signature)
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="http_exception").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred during webhook processing: {e}", exc_info=True)
        WEBHOOK_ERRORS_TOTAL.labels(provider=provider_name, event_type=event_type, error_type="unexpected_error").inc()
        WEBHOOK_EVENTS_TOTAL.labels(provider=provider_name, event_type=event_type, status="failed").inc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during webhook processing.")


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

    if payment_record.booking_id:
        booking = db.query(Booking).filter(Booking.id == payment_record.booking_id).first()
        if booking:
            lock_key = f"seat_lock:{booking.route_id}:{booking.travel_date}"
            if cache_service.is_available():
                cache_service.delete(lock_key)
        
        booking_service = BookingService(db)
        if not await booking_service.confirm_booking_payment(
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            payment_status="completed",
        ):
            raise HTTPException(status_code=500, detail="Failed to confirm booking payment.")
        return {"success": True, "message": "Payment verified and booking confirmed."}
    
    else:
        unlocked_route = db.query(UnlockedRoute).filter(UnlockedRoute.payment_id == payment_record.id).first()
        if unlocked_route:
            return {"success": True, "message": "Payment verified and route unlocked."}

        raise HTTPException(status_code=400, detail="Payment not linked to any booking or unlock.")


@router.get("/redirect/{route_id}")
async def get_redirect_url(
    route_id: str,
    request: Request,
    partner: str = "RailYatri",
    passengers: int = 1,
    travel_date: Optional[str] = Query(None), # Keeping as str for now, conversion will be handled later if needed
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a cached redirect URL to partner booking site for commission earning.
    """
    # Get route details
    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Determine route type from segments
    route_type = "train"  # Default
    if route.segments:
        # Check first segment's mode
        first_segment = route.segments[0] if isinstance(route.segments, list) else route.segments
        if hasattr(first_segment, 'mode'):
            route_type = first_segment.mode
        elif isinstance(first_segment, dict):
            route_type = first_segment.get('mode', 'train')

    # Capture fraud prevention data
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session_id = current_user.id # This is a placeholder; ideally a dedicated session ID

    # --- Fallback Logic Start ---
    original_partner = partner
    current_partner_health = redirect_service.get_partner_health(original_partner)
    
    if current_partner_health != "UP":
        logger.warning(f"Primary partner '{original_partner}' is {current_partner_health}. Attempting fallback.")
        alternative_partner = redirect_service.find_healthy_alternative_partner(
            current_partner=original_partner,
            route_type=route_type,
            source=route.source,
            destination=route.destination
        )
        if alternative_partner:
            partner = alternative_partner
            logger.info(f"Fallback successful to partner: '{partner}'")
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Primary partner '{original_partner}' is unavailable and no healthy alternative found for route type '{route_type}'."
            )
    else:
        logger.info(f"Primary partner '{original_partner}' is UP.")

    # --- Fallback Logic End ---

    # Generate redirect URL
    redirect_url, cache_key = redirect_service.generate_redirect_url(
        partner=partner, # Use potentially updated partner
        route_type=route_type,
        source=route.source,
        destination=route.destination,
        date=travel_date,  # Use dynamic travel_date
        passengers=passengers
    )

    if not redirect_url:
        raise HTTPException(status_code=500, detail=f"Failed to generate redirect URL for partner '{partner}'.")

    # Create commission tracking record
    commission_record = CommissionTracking(
        user_id=current_user.id,
        route_id=route_id,
        source=route.source,
        destination=route.destination,
        route_type=route_type,
        travel_date=travel_date,  # Use dynamic travel_date
        passengers=passengers,
        partner=partner, # Use potentially updated partner
        commission_rate=redirect_service.get_partner_commission_rate(partner),
        tracking_id=cache_key.split(':')[1],  # Extract hash from cache_key
        redirect_url=redirect_url,
        cache_key=cache_key,
        status="redirected",
        ip_address=client_ip,  # Captured from request
        user_agent=user_agent,  # Captured from request headers
        session_id=session_id   # Captured (temporary using user_id)
    )
    db.add(commission_record)
    db.commit()

    # Log redirect for analytics
    logger.info(f"Generated redirect for user {current_user.id}: {partner} - {route_type} - {cache_key}")

    return {
        "redirect_url": redirect_url,
        "partner": partner,
        "commission_rate": redirect_service.get_partner_commission_rate(partner),
        "route_type": route_type,
        "cache_key": cache_key
    }


@router.post("/commission/conversion")
async def report_conversion(
    tracking_id: str,
    amount: float,
    currency: str = "USD",
    partner: str = None,
    db: Session = Depends(get_db),
):
    """
    Partner webhook endpoint to report commission conversions.
    Updates commission tracking record when a booking/conversion occurs.
    """
    # Find the commission tracking record
    commission_record = db.query(CommissionTracking).filter(
        CommissionTracking.tracking_id == tracking_id
    ).first()

    if not commission_record:
        raise HTTPException(status_code=404, detail="Commission tracking record not found")

    # Update the record with conversion details
    commission_record.status = "converted"
    commission_record.commission_amount = amount
    commission_record.converted_at = datetime.utcnow()

    # If partner provided, validate it matches
    if partner and commission_record.partner != partner:
        logger.warning(f"Partner mismatch in conversion report: expected {commission_record.partner}, got {partner}")

    db.commit()

    logger.info(f"Commission conversion reported: {tracking_id} - {amount} {currency}")

    return {"success": True, "message": "Conversion recorded successfully"}


@router.post("/commission/payout")
async def report_payout(
    tracking_id: str,
    amount: float,
    currency: str = "USD",
    partner: str = None,
    db: Session = Depends(get_db),
):
    """
    Partner webhook endpoint to report commission payouts.
    Updates commission tracking record when payment is received.
    """
    # Find the commission tracking record
    commission_record = db.query(CommissionTracking).filter(
        CommissionTracking.tracking_id == tracking_id
    ).first()

    if not commission_record:
        raise HTTPException(status_code=404, detail="Commission tracking record not found")

    # Update the record with payout details
    commission_record.status = "paid"
    commission_record.commission_amount = amount

    # If partner provided, validate it matches
    if partner and commission_record.partner != partner:
        logger.warning(f"Partner mismatch in payout report: expected {commission_record.partner}, got {partner}")

    db.commit()

    logger.info(f"Commission payout reported: {tracking_id} - {amount} {currency}")

    return {"success": True, "message": "Payout recorded successfully"}


# -----------------------------------------------------------------------------
# Utilities: unlocked routes
# -----------------------------------------------------------------------------
@router.get("/unlocked-routes")
async def get_unlocked_routes_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return route IDs previously unlocked by the current user."""
    unlock_service = UnlockService(db)
    unlocked = unlock_service.get_unlocked_routes_by_user(str(current_user.id))
    return {"routes": [u.route_id for u in unlocked]}
