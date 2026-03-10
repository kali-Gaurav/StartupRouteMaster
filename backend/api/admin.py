import asyncio
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, Query, Header, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List
import logging

from database import get_db
from schemas import AdminBookingSchema
from services.booking_service import BookingService
from database.models import Disruption, CommissionTracking, Booking, User, Payment, EscrowStatus
from database.config import Config

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# Constants for file storage
MEDIA_DIR = "media"
TICKETS_DIR = os.path.join(MEDIA_DIR, "tickets")

# Ensure directories exist
os.makedirs(TICKETS_DIR, exist_ok=True)


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
        bookings = db.query(Booking).options(joinedload(Booking.user), joinedload(Booking.payment)).order_by(Booking.created_at.desc()).limit(limit).offset(offset).all()

        return {
            "success": True,
            "bookings": bookings,
            "count": len(bookings),
            "total": db.query(Booking).count(),
        }
    except Exception as e:
        logger.error(f"Failed to get bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get bookings")


@router.get("/bookings/stats")
async def get_booking_stats(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Get booking statistics, including revenue per mode (admin only)."""
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
    status: str = Query(None, pattern="^(pending|completed|failed)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Filter bookings by payment status (admin only)."""
    try:
        query = db.query(Booking).options(joinedload(Booking.user), joinedload(Booking.payment)).order_by(Booking.created_at.desc())

        if status:
            query = query.filter(Booking.payment_status == status)

        bookings = query.limit(limit).offset(offset).all()

        # build list of booking dicts including payment info
        booking_list = []
        for b in bookings:
            payment = b.payment[0] if b.payment else None
            booking_list.append({
                "id": str(b.id),
                "user_email": b.user.email if b.user else "N/A",
                "user_phone": b.user.phone_number if b.user else "N/A",
                "route_id": str(b.route_id),
                "travel_date": b.travel_date.isoformat() if b.travel_date else "N/A",
                "status": b.booking_status,
                "amount": b.amount_paid,
                "pnr": b.pnr_number,
                "created_at": b.created_at.isoformat() if b.created_at else "N/A",
                "payment_id": payment.id if payment else None,
                "payment_status": b.payment_status,
                "amount_paid": b.amount_paid,
            })

        return {
            "success": True,
            "bookings": booking_list,
            "count": len(bookings),
        }
    except Exception as e:
        logger.error(f"Failed to filter bookings: {e}")
        raise HTTPException(status_code=500, detail="Failed to filter bookings")


@router.post("/etl-sync")
async def trigger_etl_sync(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Trigger ETL sync from railway_data.db to database.
    Only callable by admin.
    """
    try:
        from etl.sqlite_to_postgres import run_etl

        # Run ETL without blocking the event loop
        results = await asyncio.to_thread(run_etl)

        from datetime import datetime
        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Synced {results.get('stations_synced', 0)} stations and {results.get('segments_created', 0)} segments"
        }
    except Exception as e:
        logger.error(f"ETL sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"ETL sync failed: {str(e)}")


@router.post("/reload-graph")
async def reload_route_engine_graph(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Admin endpoint to reload the in-memory route-engine graph from DB/cache."""
    try:
        from core.route_engine import route_engine
        await route_engine.initialize()
        logger.info("Route engine graph reloaded successfully")
        return {"status": "success", "message": "Route engine graph is reloaded and ready."}
    except Exception as e:
        logger.error(f"Failed to reload route engine graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload engine: {e}")


@router.post("/perf-check", status_code=202)
async def trigger_performance_check(
    background_tasks: BackgroundTasks,
    stations: int = Query(200, description="Number of synthetic stations to build for the check"),
    route_length: int = Query(6, description="Synthetic route length"),
    queries: int = Query(200, description="Number of synthetic queries to run"),
    ml_enabled: bool = Query(True, description="Include ML ranking in the benchmark"),
    _: bool = Depends(verify_admin_token),
):
    """Trigger an asynchronous performance check and push SLA metrics to Prometheus."""
    try:
        from services.perf_check import run_perf_check
        background_tasks.add_task(run_perf_check, stations, route_length, queries, ml_enabled)
        return {"status": "accepted", "message": "Performance check scheduled"}
    except Exception as e:
        logger.error(f"Failed to schedule perf check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/perf-check/status")
async def get_performance_check_status(_: bool = Depends(verify_admin_token)):
    """Return last performance-check result (if any)."""
    try:
        from services.perf_check import get_last_result
        last = get_last_result()
        return {"status": "ok", "last": last}
    except Exception as e:
        logger.error(f"Failed to fetch perf-check status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich-trains")
async def admin_enrich_trains(
    train_numbers: List[str],
    date: str = Query("today"),
    per_segment: bool = Query(False),
    _: bool = Depends(verify_admin_token),
):
    """Admin endpoint that forwards enrich request to the RouteMaster agent service."""
    try:
        from services.routemaster_client import enrich_trains_remote
        result = await enrich_trains_remote(train_numbers, date=date, use_disha=True, per_segment=per_segment)
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Failed to call routemaster agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disruptions")
async def create_disruption(
    route_id: str = Query(..., description="Route ID"),
    disruption_type: str = Query(..., description="Type: delay, cancellation, diversion"),
    description: str = Query("", description="Description of disruption"),
    disruption_date: str = Query(..., description="Date in YYYY-MM-DD"),
    start_time: str = Query(None, description="Start time in ISO format"),
    end_time: str = Query(None, description="End time in ISO format"),
    severity: str = Query("minor", description="Severity: minor, major, critical"),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Create a disruption override for real-time alerts."""
    try:
        from datetime import datetime
        try:
            d_date = datetime.fromisoformat(disruption_date).date()
            s_time = datetime.fromisoformat(start_time) if start_time else None
            e_time = datetime.fromisoformat(end_time) if end_time else None
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Invalid date/time format: {ve}")

        disruption = Disruption(
            route_id=route_id,
            disruption_type=disruption_type,
            description=description,
            disruption_date=d_date,
            start_time=s_time,
            end_time=e_time,
            severity=severity,
            status="active"
        )
        db.add(disruption)
        db.commit()
        db.refresh(disruption)
        return {"success": True, "disruption": disruption}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create disruption: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create disruption: {e}")


@router.get("/disruptions")
async def get_disruptions(
    status: str = Query("active", description="Filter by status"),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Get active disruptions for real-time alerts."""
    try:
        disruptions = db.query(Disruption).filter(Disruption.status == status).all()
        return {"success": True, "disruptions": disruptions}
    except Exception as e:
        logger.error(f"Failed to get disruptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get disruptions: {e}")


@router.put("/disruptions/{disruption_id}/resolve")
async def resolve_disruption(
    disruption_id: str,
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Resolve a disruption."""
    try:
        disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
        if not disruption:
            raise HTTPException(status_code=404, detail="Disruption not found")
        disruption.status = "resolved"
        db.commit()
        return {"success": True, "message": "Disruption resolved"}
    except Exception as e:
        logger.error(f"Failed to resolve disruption: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve disruption: {e}")


@router.post("/bookings/{booking_id}/manual-update")
async def update_booking_manual(
    booking_id: str,
    status: str = Query(..., pattern="^(confirmed|cancelled|ticket_sent|failed)$"),
    pnr: str = Query(None),
    notes: str = Query(None),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Manually update booking status and PNR (admin only)."""
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        old_status = booking.booking_status
        booking.booking_status = status
        if pnr:
            booking.pnr_number = pnr
        
        # Update notes in booking_details if it's a dict
        if notes:
            details = dict(booking.booking_details or {})
            details["admin_notes"] = notes
            booking.booking_details = details
            
        db.commit()
        
        # Task 17: Audit Log
        from services.audit_service import log_audit
        log_audit(db, "Booking", booking.id, "MANUAL_STATUS_UPDATE", old_value=old_status, new_value=status, performed_by="ADMIN", reason=notes)
        
        return {"success": True, "message": f"Booking {booking_id} updated to {status}"}
    except Exception as e:
        logger.error(f"Failed to update booking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update booking")


@router.post("/bookings/{booking_id}/verify-escrow")
async def verify_escrow_payment(
    booking_id: str,
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 13: Manual 'Mark as Paid' Action (admin only).
    Task 41: State Machine Guard - only verify if UTR submitted.
    """
    from database.models import EscrowStatus
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Task 41: Guard
        if booking.escrow_status != EscrowStatus.UTR_SUBMITTED:
             raise HTTPException(status_code=400, detail=f"Cannot verify booking in {booking.escrow_status} state. Must be UTR_SUBMITTED.")
        
        old_status = booking.escrow_status.value if hasattr(booking.escrow_status, 'value') else str(booking.escrow_status)
        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "Payment verified. Seat securing in progress."
        
        # For UNLOCK service, we can complete it immediately
        if booking.service_type == "UNLOCK":
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.is_unlocked = True
            booking.escrow_message = "Route details unlocked successfully."
            
        db.commit()
        
        # Task 17: Audit Log
        from services.audit_service import log_audit
        log_audit(db, "Booking", booking.id, "ESCROW_VERIFICATION", old_value=old_status, new_value=str(booking.escrow_status), performed_by="ADMIN", reason="Manual UTR verification")
        
        return {
            "success": True,
            "message": f"Escrow verified for booking {booking_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify escrow: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to verify escrow")


@router.post("/bookings/{booking_id}/start-booking")
async def initiate_manual_booking(
    booking_id: str,
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 21: "Initiate Booking" State.
    Moves state to BOOKING_INITIATED to notify user that agent is working.
    """
    from database.models import EscrowStatus
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Task 41: Guard
        if booking.escrow_status != EscrowStatus.VERIFIED:
             raise HTTPException(status_code=400, detail=f"Cannot initiate booking. Escrow must be VERIFIED first. Current: {booking.escrow_status}")
        
        old_status = booking.escrow_status.value if hasattr(booking.escrow_status, 'value') else str(booking.escrow_status)
        booking.escrow_status = EscrowStatus.BOOKING_INITIATED
        booking.escrow_message = "Agent is currently booking your ticket on IRCTC. Please wait..."
        
        db.commit()
        
        # Task 17: Audit Log
        from services.audit_service import log_audit
        log_audit(db, "Booking", booking.id, "BOOKING_START", old_value=old_status, new_value="BOOKING_INITIATED", performed_by="ADMIN")
        
        return {
            "success": True,
            "message": f"Booking process started for {booking_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate booking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to initiate booking")


@router.get("/pending-verifications")
async def get_pending_verifications(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 11: Admin UTR Verification Panel (Backend).
    Lists all bookings where UTR is submitted but not yet verified.
    """
    from database.models import EscrowStatus
    try:
        bookings = db.query(Booking).filter(
            Booking.escrow_status == EscrowStatus.UTR_SUBMITTED
        ).order_by(Booking.created_at.desc()).all()
        
        return {
            "success": True,
            "bookings": bookings,
            "count": len(bookings)
        }
    except Exception as e:
        logger.error(f"Failed to get pending verifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending verifications")


@router.get("/unmatched-funds")
async def get_unmatched_funds(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 14: Unmatched Funds Ledger.
    Lists bank transactions that haven't been matched to any booking.
    """
    from database.models import BankTransaction
    try:
        transactions = db.query(BankTransaction).filter(
            BankTransaction.status == "PENDING"
        ).order_by(BankTransaction.received_at.desc()).all()
        
        return {
            "success": True,
            "transactions": transactions,
            "count": len(transactions)
        }
    except Exception as e:
        logger.error(f"Failed to get unmatched funds: {e}")
        raise HTTPException(status_code=500, detail="Failed to get unmatched funds")


@router.get("/bookings/{booking_id}/passenger-export")
async def export_passenger_details(
    booking_id: str,
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 22: Passenger Data Export (Backend).
    Returns formatted string for easy copy-pasting into IRCTC.
    """
    from database.models import PassengerDetails
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        passengers = db.query(PassengerDetails).filter(PassengerDetails.booking_id == booking_id).all()
        
        formatted_list = []
        for p in passengers:
            formatted_list.append(f"Name: {p.full_name}, Age: {p.age}, Gender: {p.gender}")
            
        summary = "\n".join(formatted_list)
        
        return {
            "success": True,
            "passengers": [
                {"name": p.full_name, "age": p.age, "gender": p.gender} for p in passengers
            ],
            "copy_paste_string": summary
        }
    except Exception as e:
        logger.error(f"Failed to export passengers: {e}")
        raise HTTPException(status_code=500, detail="Failed to export passengers")


@router.get("/commission/reconciliation")
async def get_commission_reconciliation(
    month: str = Query(..., description="Month in YYYY-MM format"),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """Get monthly commission reconciliation report."""
    try:
        from datetime import datetime
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        commissions = db.query(CommissionTracking).filter(
            CommissionTracking.redirected_at >= start_date,
            CommissionTracking.redirected_at < end_date
        ).all()
        
        total_redirects = len(commissions)
        total_conversions = sum(1 for c in commissions if c.status == "converted")
        total_earnings = sum(c.commission_amount for c in commissions if c.commission_amount > 0)
        
        partner_breakdown = {}
        for c in commissions:
            if c.partner not in partner_breakdown:
                partner_breakdown[c.partner] = {"redirects": 0, "conversions": 0, "earnings": 0.0}
            partner_breakdown[c.partner]["redirects"] += 1
            if c.status == "converted":
                partner_breakdown[c.partner]["conversions"] += 1
                partner_breakdown[c.partner]["earnings"] += c.commission_amount
        
        return {
            "success": True,
            "period": month,
            "total_redirects": total_redirects,
            "total_conversions": total_conversions,
            "conversion_rate": total_conversions / total_redirects if total_redirects > 0 else 0,
            "total_earnings": total_earnings,
            "partner_breakdown": partner_breakdown
        }
    except Exception as e:
        logger.error(f"Failed to get commission reconciliation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get reconciliation: {e}")


@router.post("/bookings/{booking_id}/upload-ticket")
async def upload_ticket_pdf(
    booking_id: str,
    file: UploadFile = File(...),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 26: Ticket PDF Uploader (Backend).
    Saves the E-ticket PDF and updates the booking record.
    """
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Save file to media/tickets/<booking_id>.pdf
        file_path = os.path.join(TICKETS_DIR, f"{booking_id}.pdf")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update booking
        old_url = booking.ticket_pdf_url
        booking.ticket_pdf_url = f"/media/tickets/{booking_id}.pdf"
        booking.escrow_status = EscrowStatus.COMPLETED
        booking.booking_status = "confirmed"
        booking.escrow_message = "Ticket booked successfully! You can download it now."
        db.commit()

        # Task 17: Audit Log
        from services.audit_service import log_audit
        log_audit(db, "Booking", booking.id, "TICKET_UPLOAD", old_value=old_url, new_value=booking.ticket_pdf_url, performed_by="ADMIN")

        return {
            "success": True,
            "message": "Ticket PDF uploaded and booking completed",
            "url": booking.ticket_pdf_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload ticket: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload ticket")


@router.post("/bookings/{booking_id}/fail")
async def fail_booking(
    booking_id: str,
    reason: str = Query(..., description="Reason for failure (e.g., Sold Out)"),
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
):
    """
    Task 29: Booking Failure Handling.
    Marks a booking as FAILED and triggers the refund flow process.
    """
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        old_status = booking.escrow_status.value if hasattr(booking.escrow_status, 'value') else str(booking.escrow_status)
        booking.escrow_status = EscrowStatus.FAILED
        booking.booking_status = "failed"
        booking.escrow_message = f"Booking failed: {reason}. Refund will be processed."
        db.commit()

        # Task 17: Audit Log
        from services.audit_service import log_audit
        log_audit(db, "Booking", booking.id, "BOOKING_FAILURE", old_value=old_status, new_value="FAILED", performed_by="ADMIN", reason=reason)

        return {
            "success": True,
            "message": f"Booking {booking_id} marked as FAILED. Reason: {reason}"
        }
    except Exception as e:
        logger.error(f"Failed to fail booking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark booking as failed")
