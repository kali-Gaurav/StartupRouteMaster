"""
User Dashboard API Routes - REST endpoints for user profile and dashboard data.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database.session import get_db
from services.booking_service import get_booking_service
from services.payment_service import get_payment_service
from core.auth import get_current_user

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.get("/dashboard")
async def get_user_dashboard(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get dashboard summary for user.

    Returns:
    {
        "total_bookings": 5,
        "total_spent": 15000.50,
        "upcoming_bookings": 2,
        "cancelled_bookings": 1,
        "recent_activity": [...]
    }
    """
    try:
        booking_service = get_booking_service(db)

        # Get dashboard summary from service
        dashboard_data = await booking_service.get_dashboard_summary(current_user.id, db)

        return {
            "total_bookings": dashboard_data.get("total_bookings", 0),
            "total_spent": dashboard_data.get("total_spent", 0),
            "upcoming_bookings": dashboard_data.get("upcoming_bookings", 0),
            "cancelled_bookings": dashboard_data.get("cancelled_bookings", 0),
            "recent_activity": dashboard_data.get("recent_activity", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching dashboard summary"
        )


@router.get("/bookings")
async def get_user_bookings(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, description="Filter by booking status")
):
    """
    Get user booking history with pagination and optional status filter.

    Supports filtering by: initiated, payment_pending, confirmed, cancelled, failed, waitlist

    Returns:
    {
        "bookings": [...],
        "total": 25,
        "limit": 50,
        "offset": 0
    }
    """
    try:
        booking_service = get_booking_service(db)

        # Get booking history with optional status filter
        bookings = await booking_service.list_user_bookings(
            current_user.id, status_filter, limit, offset
        )

        return {
            "bookings": [
                {
                    "booking_id": b.id,
                    "pnr_number": b.pnr_number,
                    "status": b.booking_status,
                    "total_amount": b.total_amount or 0,
                    "travel_date": b.travel_date,
                    "train_number": b.train_number,
                    "from_station": b.from_station,
                    "to_station": b.to_station,
                    "class_type": b.class_type,
                    "created_at": b.created_at
                }
                for b in bookings
            ],
            "total": len(bookings),
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching bookings for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching booking history"
        )


@router.get("/payments")
async def get_user_payments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get user payment history with pagination.

    Returns:
    {
        "payments": [...],
        "total": 5,
        "limit": 50,
        "offset": 0
    }
    """
    try:
        payment_service = get_payment_service(db)

        # Get payment history
        payments = await payment_service.get_user_payment_history(
            current_user.id, limit, offset
        )

        return {
            "payments": [
                {
                    "payment_id": p.id if hasattr(p, 'id') else p.get('id'),
                    "booking_id": p.booking_id if hasattr(p, 'booking_id') else p.get('booking_id'),
                    "amount": p.amount if hasattr(p, 'amount') else p.get('amount'),
                    "status": p.status.value if hasattr(p, 'status') else p.get('status'),
                    "payment_method": p.payment_method if hasattr(p, 'payment_method') else p.get('payment_method'),
                    "created_at": p.created_at if hasattr(p, 'created_at') else p.get('created_at'),
                    "transaction_id": p.transaction_id if hasattr(p, 'transaction_id') else p.get('transaction_id')
                }
                for p in payments
            ],
            "total": len(payments),
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payments for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching payment history"
        )


@router.get("/tickets")
async def get_user_tickets(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get user's issued tickets from confirmed bookings.

    Returns:
    {
        "tickets": [
            {
                "ticket_id": "...",
                "booking_id": "...",
                "pnr_number": "...",
                "passenger_name": "...",
                "train_number": "...",
                "from_station": "...",
                "to_station": "...",
                "travel_date": "...",
                "seat_number": "...",
                "class": "...",
                "coach": "...",
                "status": "issued"
            }
        ],
        "total": 10
    }
    """
    try:
        booking_service = get_booking_service(db)

        # Get user tickets from confirmed bookings
        tickets = await booking_service.get_user_tickets(current_user.id, db)

        return {
            "tickets": tickets,
            "total": len(tickets)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tickets for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching tickets"
        )


@router.get("/profile")
async def get_user_profile(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get user profile information.

    Returns:
    {
        "user_id": "...",
        "email": "user@example.com",
        "full_name": "John Doe",
        "phone_number": "+919876543210",
        "profile_picture_url": "...",
        "role": "user",
        "verified": true,
        "verified_at": "2024-01-15T10:30:00",
        "created_at": "2024-01-10T10:30:00",
        "last_active_at": "2024-01-20T15:45:00",
        "preferences": {
            "notification_email": true,
            "notification_sms": true
        }
    }
    """
    try:
        from services.user_service import get_user_service
        user_service = get_user_service(db)

        # Get user profile
        user_profile = await user_service.get_user_profile(current_user.id)

        if not user_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return {
            "user_id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "phone_number": current_user.phone_number,
            "profile_picture_url": user_profile.get("profile_picture_url"),
            "role": current_user.role,
            "verified": current_user.is_verified,
            "verified_at": current_user.verified_at,
            "created_at": current_user.created_at,
            "last_active_at": current_user.last_active_at,
            "preferences": current_user.preferences or {}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching user profile"
        )


@router.get("/saved-routes")
async def get_saved_routes(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get user's saved routes.

    Returns:
    {
        "routes": [
            {
                "id": "route_...",
                "name": "Office Route",
                "from_station": "New Delhi",
                "to_station": "Mumbai Central",
                "created_at": "2024-01-15T10:30:00"
            }
        ],
        "total": 3
    }
    """
    try:
        # TODO: Implement saved routes service
        # For now, return empty list
        return {
            "routes": [],
            "total": 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching saved routes for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching saved routes"
        )
