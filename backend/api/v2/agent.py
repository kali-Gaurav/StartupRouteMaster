from fastapi import APIRouter, Depends, HTTPException, Body, Path, UploadFile, File
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Booking, EscrowStatus, BookingStatus
from api.dependencies import get_current_user
import os
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

def verify_agent_role(user: User):
    if user.role != "agent" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied. Agent role required.")

@router.get("/tasks")
async def get_pending_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List all verified bookings awaiting agent action."""
    verify_agent_role(user)
    
    tasks = db.query(Booking).filter(
        Booking.service_type == "AGENT_BOOKING",
        Booking.escrow_status == EscrowStatus.VERIFIED,
        Booking.agent_id == None
    ).all()
    
    return tasks

@router.post("/{booking_id}/claim")
async def claim_task(
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Assign an agent to a specific booking."""
    verify_agent_role(user)
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.agent_id:
        raise HTTPException(status_code=400, detail="Task already claimed by another agent")

    booking.agent_id = user.id
    booking.escrow_message = f"Agent {user.profile.name if user.profile else 'Guide'} has started working on your booking."
    db.commit()
    
    return {"message": "Task claimed successfully", "booking_id": booking_id}

@router.post("/{booking_id}/fulfill")
async def fulfill_task(
    booking_id: str = Path(...),
    pnr: str = Body(..., embed=True),
    ticket_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Complete the booking by uploading the final ticket PDF."""
    verify_agent_role(user)
    
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.agent_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not assigned to you")

    # 1. Save Ticket PDF
    upload_dir = "media/tickets/confirmed"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{booking_id}.pdf"
    
    with open(file_path, "wb") as f:
        f.write(await ticket_file.read())

    # 2. Update Booking Status
    booking.pnr_number = pnr
    booking.escrow_status = EscrowStatus.COMPLETED
    booking.booking_status = BookingStatus.CONFIRMED.value
    booking.escrow_message = "Ticket confirmed by RouteMaster Agent. Safe journey!"
    
    # Update transaction history
    details = dict(booking.booking_details or {})
    details['ticket_path'] = file_path
    booking.booking_details = details
    
    db.commit()
    
    return {"message": "Booking fulfilled!", "pnr": pnr}
