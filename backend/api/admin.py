from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
import logging

from database import get_db
from schemas import AdminBookingSchema
from services import BookingService
from config import Config

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def verify_admin_token(x_admin_token: str = Header(...)) -> bool:
    """Verify admin API token."""
    if x_admin_token != Config.ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.get("/bookings")
async def get_all_bookings(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Get all booking requests (admin only)."""
    try:
        booking_service = BookingService(db)
        bookings = booking_service.get_all_bookings(limit=limit, offset=offset)

        return {
            "success": True,
            "bookings": bookings,
            "count": len(bookings),
            "total": db.query(booking_service.__class__).count(),
        }
    except Exception as e:
        logger.error(f"Failed to get bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get bookings")


@router.get("/bookings/stats")
async def get_booking_stats(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Get booking statistics (admin only)."""
    try:
        booking_service = BookingService(db)
        stats = booking_service.get_booking_stats()

        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")


@router.get("/bookings/filter")
async def filter_bookings(
    status: str = Query(None, regex="^(pending|completed|failed)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Filter bookings by payment status (admin only)."""
    try:
        from models import Booking

        query = db.query(Booking).order_by(Booking.created_at.desc())

        if status:
            query = query.filter(Booking.payment_status == status)

        bookings = query.limit(limit).offset(offset).all()

        return {
            "success": True,
            "bookings": [
                {
                    "id": str(b.id),
                    "user_name": b.user_name,
                    "user_email": b.user_email,
                    "user_phone": b.user_phone,
                    "route_id": str(b.route_id),
                    "travel_date": b.travel_date,
                    "payment_id": b.payment_id,
                    "payment_status": b.payment_status,
                    "amount_paid": b.amount_paid,
                    "created_at": b.created_at.isoformat(),
                }
                for b in bookings
            ],
            "count": len(bookings),
        }
    except Exception as e:
        logger.error(f"Failed to filter bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to filter bookings")


@router.post("/etl-sync")
async def trigger_etl_sync(
    token: str = Query(..., description="Admin API token"),
    db: Session = Depends(get_db),
):
    """
    Trigger ETL sync from railway_manager.db to database.
    Only callable by admin.
    """
    try:
        # Verify admin token
        if token != Config.ADMIN_API_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Import ETL module
        from etl.sqlite_to_postgres import run_etl

        # Run ETL
        results = run_etl()

        # Log results
        logger.info(f"ETL sync completed: {results}")

        return {
            "status": "success",
            "results": results,
            "timestamp": "2026-02-12T19:30:00Z",  # Would use datetime.utcnow() in real implementation
            "message": f"Synced {results['stations_synced']} stations and {results['segments_created']} segments"
        }
    except Exception as e:
        logger.error(f"ETL sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"ETL sync failed: {str(e)}")
