"""
🔥 BOOKINGS API V3 - Complete Booking Lifecycle
Handles booking creation, state management, and payment flow.
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database.session import get_db, SessionUser
from database.models import (
    User, Booking, EscrowStatus,
    BookingAuditLog
)
from services.payment_service import PaymentService
from services.booking.pnr_verification import PNRVerificationService
from services.inventory.service import InventoryService
from core.route_engine import get_route_engine
from utils.responses import success_response, error_response, v3_response
from api.dependencies import get_current_user

logger = logging.getLogger("bookings_v3")

router = APIRouter(prefix="/api/v3/bookings", tags=["Bookings"])

# pyrefly: ignore [missing-import]
from pydantic import BaseModel

# Dependency for PaymentService
def get_payment_service(db: Session = Depends(get_db)):
    return PaymentService(db)

# Dependency for InventoryService
def get_inventory_service():
    return InventoryService()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PassengerInfo(BaseModel):
    """Passenger details for booking"""
    name: str
    age: int
    gender: str  # "M", "F", "O"
    phone: Optional[str] = None
    email: Optional[str] = None
    aadhar_id: Optional[str] = None

class BookingCreateRequest(BaseModel):
    """Create booking request"""
    route_id: str
    segment_indices: List[int]  # Which segments in route
    passengers: List[PassengerInfo]
    travel_date: str
    budget_category: Optional[str] = None

class BookingCreateResponse(BaseModel):
    """Booking creation response"""
    booking_id: str
    status: str
    amount: float
    payment_url: str
    expires_at: str


# ============================================================================
# ENDPOINT: Create Booking
# ============================================================================

@router.post("/create", response_model=Dict[str, Any])
async def create_booking(
    request: BookingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
    inventory_service: InventoryService = Depends(get_inventory_service)
):
    """
    Create a new booking for authenticated user.
    
    Workflow:
    1. Validate route still available
    2. Reserve seats temporarily
    3. Create booking record
    4. Initialize payment
    5. Return payment URL
    """
    logger.info(f"📝 Creating booking for user {current_user.id}, "
               f"route {request.route_id}, {len(request.passengers)} passengers")
    
    # payment_service injected via dependency
    
    try:
        # Step 1: Validate route availability
        is_valid, error_msg = await get_route_engine().validate_booking(
            route_id=request.route_id,
            passenger_count=len(request.passengers),
            travel_date=request.travel_date
        )
        
        if not is_valid:
            logger.error(f"❌ Route validation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Step 2: Reserve seats
        reservation_ids = []
        try:
            travel_date_obj = datetime.strptime(request.travel_date, "%Y-%m-%d").date()
        except Exception:
            travel_date_obj = None

        try:
            trip_id = int(request.route_id)
        except Exception:
            trip_id = request.route_id

        for segment_idx in request.segment_indices:
            for passenger_idx in range(len(request.passengers)):
                reservation = inventory_service.reserve_seat_temporary(
                    db=db,
                    trip_id=trip_id,
                    travel_date=travel_date_obj,
                    coach_type="GN",
                    booking_id=f"{request.route_id}_{segment_idx}_{passenger_idx}",
                    lock_minutes=15
                )
                if isinstance(reservation, dict):
                    success = reservation.get("success", False)
                else:
                    success = getattr(reservation, "success", False)
                if success:
                    reservation_ids.append(str(reservation.trip_id if hasattr(reservation, 'trip_id') else request.route_id))
                else:
                    logger.warning(f"Seat reservation failed for route {request.route_id}, segment {segment_idx}: {getattr(reservation, 'error', 'unknown')}")

        logger.info(f"✅ Reserved {len(reservation_ids)} seats")

        # Step 3: Calculate fare
        total_amount = 2000.0  # ₹2000 default (would be calculated from route)
        try:
            route_details = await get_route_engine().get_route_details(request.route_id)
            if route_details and isinstance(route_details, dict):
                total_amount = float(route_details.get("total_fare", total_amount) or total_amount)
        except Exception as e:
            logger.warning(f"Unable to hydrate fare for route {request.route_id}: {e}")
        
        # Step 4: Create booking record
        booking = Booking(
            user_id=current_user.id,
            travel_date=request.travel_date,
            booking_status="pending",
            escrow_status=EscrowStatus.CREATED,
            amount_paid=0.0,
            total_amount=total_amount,
            route_id=request.route_id,
            segment_indices=",".join(map(str, request.segment_indices)),
            reservation_ids=",".join(reservation_ids),
            passenger_count=len(request.passengers)
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        
        logger.info(f"✅ Booking created: {booking.id}")
        
        # Step 5: Initialize payment
        payment_order = await payment_service.create_order(
            amount_rupees=total_amount,
            receipt_id=booking.id,
            customer_email=current_user.email,
            description=f"Booking {request.route_id} for {len(request.passengers)} passengers"
        )
        
        if not payment_order.get("success"):
            # Release reserved seats on payment failure
            logger.error(f"❌ Payment initialization failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment initialization failed"
            )
        
        # Step 6: Update booking with payment order
        booking.escrow_status = EscrowStatus.PAYMENT_PROCESSING
        booking.payment_order_id = payment_order["order_id"]
        db.commit()
        
        # Step 7: Log audit
        audit = BookingAuditLog(
            booking_id=booking.id,
            action="CREATED",
            actor_type="SYSTEM",
            extra_data={"request": request.dict()}
        )
        db.add(audit)
        db.commit()
        
        return success_response({
            "booking_id": booking.id,
            "status": "PENDING_PAYMENT",
            "amount": total_amount,
            "payment_order_id": payment_order.get("order_id"),
            "payment_key_id": payment_order.get("key_id"),
            "payment_url": payment_order.get("payment_url") or "",
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Booking creation failed: {e}")
        return error_response(
            message="Booking creation failed",
            error_code="BOOKING_CREATE_FAILED"
        )

# ============================================================================
# ENDPOINT: Get Booking
# ============================================================================

@router.get("/{booking_id}", response_model=Dict[str, Any])
async def get_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get booking details"""
    logger.info(f"📖 Fetching booking {booking_id}")
    
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return success_response({
        "booking_id": booking.id,
        "status": booking.booking_status,
        "escrow_status": booking.escrow_status.value,
        "travel_date": booking.travel_date.isoformat() if booking.travel_date else None,
        "amount": booking.total_amount,
        "amount_paid": booking.amount_paid,
        "pnr_number": booking.pnr_number,
        "created_at": booking.created_at.isoformat() if booking.created_at else None
    })

# ============================================================================
# ENDPOINT: List User Bookings
# ============================================================================

@router.get("", response_model=Dict[str, Any])
async def list_user_bookings(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all bookings for current user"""
    logger.info(f"📋 Listing bookings for user {current_user.id}")
    
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    
    if status_filter:
        query = query.filter(Booking.booking_status == status_filter)
    
    bookings = query.order_by(Booking.created_at.desc()).all()
    
    return success_response({
        "bookings": [
            {
                "booking_id": b.id,
                "status": b.booking_status,
                "travel_date": b.travel_date.isoformat() if b.travel_date else None,
                "amount": b.total_amount,
                "pnr_number": b.pnr_number,
                "created_at": b.created_at.isoformat() if b.created_at else None
            }
            for b in bookings
        ],
        "count": len(bookings)
    })

# ============================================================================
# ENDPOINT: Cancel Booking
# ============================================================================

@router.post("/{booking_id}/cancel", response_model=Dict[str, Any])
async def cancel_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a booking"""
    logger.info(f"❌ Cancelling booking {booking_id}")
    
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.booking_status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel booking with status {booking.booking_status}"
        )
    
    # Update status
    booking.booking_status = "cancelled"
    booking.escrow_status = EscrowStatus.CANCELLED
    
    # Log audit
    audit = BookingAuditLog(
        booking_id=booking.id,
        action="CANCELLED",
        actor_type="USER" if current_user else "SYSTEM",
        actor_id=current_user.id if current_user else "SYSTEM"
    )
    db.add(audit)
    db.commit()
    
    logger.info(f"✅ Booking {booking_id} cancelled")
    
    return success_response({
        "booking_id": booking.id,
        "status": "CANCELLED",
        "message": "Booking cancelled successfully"
    })

# ============================================================================
# ENDPOINT: Booking Health Check
# ============================================================================

@router.get("/health", response_model=Dict[str, Any])
async def bookings_health(db: Session = Depends(get_db)):
    """Health check for bookings API"""
    try:
        # Check database connectivity
        db.execute("SELECT 1")
        
        # Check pending bookings
        pending_count = db.query(Booking).filter(
            Booking.booking_status == "pending"
        ).count()
        
        return v3_response({
            "status": "HEALTHY",
            "pending_bookings": pending_count,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return v3_response(
            data={"error": str(e)},
            status="UNHEALTHY",
            status_code=503
        )
