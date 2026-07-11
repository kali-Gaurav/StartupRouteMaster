"""
Dashboard API Routes - REST endpoints for user dashboard.
Feature #2 implementation.
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database.session import get_db
from core.auth import get_current_user
from services.dashboard_service import (
    get_dashboard_service,
    DashboardService,
    BookingHistoryItem,
    PaymentHistoryItem,
    UserTicket,
    UserProfile,
    DashboardSummary
)

logger = logging.getLogger("api.dashboard")

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# =========================================================================
# SCHEMAS (Pydantic models for response validation)
# =========================================================================

from pydantic import BaseModel

class BookingHistoryResponse(BaseModel):
    booking_id: str
    pnr_number: Optional[str]
    status: str
    travel_date: Optional[str]
    from_station: Optional[str]
    to_station: Optional[str]
    amount_paid: float
    class_type: Optional[str]
    booked_at: str
    passenger_count: int


class PaymentHistoryResponse(BaseModel):
    payment_id: str
    booking_id: Optional[str]
    amount: float
    status: str
    method: Optional[str]
    created_at: str
    pnr_number: Optional[str]


class TicketResponse(BaseModel):
    booking_id: str
    pnr_number: Optional[str]
    train_number: Optional[str]
    travel_date: Optional[str]
    status: str
    passengers: List[str]
    ticket_pdf_url: Optional[str]


class UserProfileResponse(BaseModel):
    user_id: str
    full_name: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    member_since: str
    total_bookings: int
    total_spent: float
    preferences: Optional[dict]


class RecentActivityResponse(BaseModel):
    type: str
    booking_id: str
    pnr: Optional[str]
    status: str
    date: str
    amount: Optional[float]


class DashboardSummaryResponse(BaseModel):
    total_bookings: int
    total_spent: float
    upcoming_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    pending_payments: int
    recent_activity: List[RecentActivityResponse]
    member_since: str
    last_booking_date: Optional[str]


class BookingHistoryListResponse(BaseModel):
    items: List[BookingHistoryResponse]
    total: int
    limit: int
    offset: int


class PaymentHistoryListResponse(BaseModel):
    items: List[PaymentHistoryResponse]
    total: int
    limit: int
    offset: int


# =========================================================================
# ENDPOINTS
# =========================================================================

@router.get("/profile", response_model=UserProfileResponse, status_code=status.HTTP_200_OK)
async def get_profile(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get user profile and preferences.

    Returns user profile with:
    - Full name, email, phone number
    - Member since date
    - Total bookings and amount spent
    - User preferences
    
    Cached for 1 hour.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        profile = await dashboard_service.get_user_profile(user.id)

        return UserProfileResponse(
            user_id=profile.user_id,
            full_name=profile.full_name,
            email=profile.email,
            phone_number=profile.phone_number,
            member_since=profile.member_since.isoformat(),
            total_bookings=profile.total_bookings,
            total_spent=profile.total_spent,
            preferences=profile.preferences
        )

    except Exception as e:
        logger.error(f"Error fetching profile for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile"
        )


@router.get("/summary", response_model=DashboardSummaryResponse, status_code=status.HTTP_200_OK)
async def get_summary(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get dashboard summary with overview statistics.

    Returns:
    - Total bookings and total spent
    - Upcoming vs completed vs cancelled bookings
    - Pending payment count
    - Recent activity feed (last 5 bookings)
    - Member since and last booking date
    
    Cached for 1 hour.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        summary = await dashboard_service.get_dashboard_summary(user.id)

        recent_activity = [
            RecentActivityResponse(
                type=a["type"],
                booking_id=a["booking_id"],
                pnr=a.get("pnr"),
                status=a["status"],
                date=a["date"],
                amount=a.get("amount")
            )
            for a in summary.recent_activity
        ]

        return DashboardSummaryResponse(
            total_bookings=summary.total_bookings,
            total_spent=summary.total_spent,
            upcoming_bookings=summary.upcoming_bookings,
            completed_bookings=summary.completed_bookings,
            cancelled_bookings=summary.cancelled_bookings,
            pending_payments=summary.pending_payments,
            recent_activity=recent_activity,
            member_since=summary.member_since.isoformat(),
            last_booking_date=summary.last_booking_date.isoformat() if summary.last_booking_date else None
        )

    except Exception as e:
        logger.error(f"Error fetching summary for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard summary"
        )


@router.get("/bookings", response_model=BookingHistoryListResponse, status_code=status.HTTP_200_OK)
async def get_booking_history(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get user booking history with pagination.

    Query Parameters:
    - limit: Number of bookings per page (max 100, default 50)
    - offset: Starting position (default 0)

    Returns paginated list of bookings with:
    - Booking ID, PNR, status
    - Travel date and stations
    - Amount paid and class type
    - Passenger count
    
    Cached for 30 minutes.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        items, total = await dashboard_service.get_user_booking_history(
            user.id,
            limit=limit,
            offset=offset
        )

        return BookingHistoryListResponse(
            items=[
                BookingHistoryResponse(
                    booking_id=b.booking_id,
                    pnr_number=b.pnr_number,
                    status=b.status,
                    travel_date=b.travel_date.isoformat() if b.travel_date else None,
                    from_station=b.from_station,
                    to_station=b.to_station,
                    amount_paid=b.amount_paid,
                    class_type=b.class_type,
                    booked_at=b.booked_at.isoformat(),
                    passenger_count=b.passenger_count
                )
                for b in items
            ],
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error fetching booking history for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch booking history"
        )


@router.get("/payments", response_model=PaymentHistoryListResponse, status_code=status.HTTP_200_OK)
async def get_payment_history(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get user payment history with pagination.

    Query Parameters:
    - limit: Number of payments per page (max 100, default 50)
    - offset: Starting position (default 0)

    Returns paginated list of payments with:
    - Payment ID, associated booking
    - Amount and payment status
    - Payment method
    - PNR number (from associated booking)
    
    Cached for 30 minutes.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        items, total = await dashboard_service.get_user_payment_history(
            user.id,
            limit=limit,
            offset=offset
        )

        return PaymentHistoryListResponse(
            items=[
                PaymentHistoryResponse(
                    payment_id=p.payment_id,
                    booking_id=p.booking_id,
                    amount=p.amount,
                    status=p.status,
                    method=p.method,
                    created_at=p.created_at.isoformat(),
                    pnr_number=p.pnr_number
                )
                for p in items
            ],
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error fetching payment history for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment history"
        )


@router.get("/tickets", response_model=List[TicketResponse], status_code=status.HTTP_200_OK)
async def get_tickets(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get user tickets for active, upcoming, and recently used bookings.

    Returns list of tickets with:
    - Booking ID and PNR
    - Train number and travel date
    - Ticket status (active/upcoming/used)
    - List of passenger names
    - Ticket PDF URL (if available)
    
    Not paginated - returns all active tickets.
    Cached for 30 minutes.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        tickets = await dashboard_service.get_user_tickets(user.id)

        return [
            TicketResponse(
                booking_id=t.booking_id,
                pnr_number=t.pnr_number,
                train_number=t.train_number,
                travel_date=t.travel_date.isoformat() if t.travel_date else None,
                status=t.status,
                passengers=t.passengers,
                ticket_pdf_url=t.ticket_pdf_url
            )
            for t in tickets
        ]

    except Exception as e:
        logger.error(f"Error fetching tickets for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tickets"
        )


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh_dashboard_cache(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Manually refresh dashboard cache for the current user.

    Invalidates all cached dashboard data:
    - Profile cache
    - Summary cache
    - Booking/payment history caches
    - Tickets cache

    Useful when user expects fresh data immediately after an action.
    
    Returns 204 No Content on success.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        dashboard_service.invalidate_user_cache(user.id)
        logger.info(f"Dashboard cache invalidated for user {user.id}")
        return

    except Exception as e:
        logger.error(f"Error refreshing cache for {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh dashboard cache"
        )


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_dashboard_metrics(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Get dashboard service performance metrics.

    Returns service-level metrics:
    - Total operations and success rate
    - Operations breakdown by type
    - Performance data

    Useful for monitoring service health.
    """
    try:
        dashboard_service = get_dashboard_service(db)
        metrics = dashboard_service.get_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics"
        )
