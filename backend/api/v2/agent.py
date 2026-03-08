from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Booking, EscrowStatus, AuditLog, User
from services.agent_booking_service import AgentBookingService
from services.ws_manager import ws_manager
from api.dependencies import require_role # [36.3]
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent Operations"])

@router.get("/bookings/queue")
async def get_agent_queue(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    admin_or_agent: User = Depends(require_role(["agent", "admin"])) # [36.3]
):
    """
    Subtask 21.1: Fetch the prioritized queue of verified bookings.
    [21.2] Sorted by Priority (0 is highest) and then age.
    """
    offset = (page - 1) * limit
    
    # Filter for VERIFIED bookings that are either unclaimed or active for agents
    bookings = db.query(Booking).filter(
        Booking.escrow_status == EscrowStatus.VERIFIED,
        Booking.service_type == "AGENT_BOOKING",
        Booking.agent_id == None
    ).order_by(
        Booking.priority.asc(), 
        Booking.created_at.asc()
    ).offset(offset).limit(limit).all()
    
    return bookings

@router.post("/availability/toggle")
async def toggle_agent_availability(
    agent_id: str = Query(...), 
    db: Session = Depends(get_db)
):
    """
    Subtask 30.2: Toggle online/offline status for agents.
    [30.7] Records shift logs in AuditLog.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    old_status = agent.is_available
    agent.is_available = not agent.is_available
    agent.last_heartbeat = datetime.utcnow()
    
    # [30.7] Shift Logging
    action = "SHIFT_START" if agent.is_available else "SHIFT_END"
    audit = AuditLog(
        entity_type="Agent",
        entity_id=agent_id,
        action=action,
        old_value="OFFLINE" if not old_status else "ONLINE",
        new_value="ONLINE" if agent.is_available else "OFFLINE",
        performed_by=agent_id,
        reason="Manual toggle via dashboard."
    )
    db.add(audit)
    db.commit()
    
    return {
        "status": "success", 
        "is_available": agent.is_available,
        "last_heartbeat": agent.last_heartbeat
    }
@router.post("/bookings/{booking_id}/claim")
async def claim_booking(
    booking_id: str, 
    agent_id: str = Query(...), 
    db: Session = Depends(get_db),
    admin_or_agent: User = Depends(require_role(["agent", "admin"])) # [36.3]
):
    """
    [22.1] Atomic Claim Logic: Uses SELECT FOR UPDATE.
    [22.2] Capacity Guard: Limits agent to 3 active bookings.
    [22.6] Conflict Handling: Returns 409 if already claimed.
    """
    # 1. Capacity Check
    active_claims = db.query(Booking).filter(
        Booking.agent_id == agent_id,
        Booking.escrow_status == EscrowStatus.BOOKING_INITIATED
    ).count()
    
    if active_claims >= 3:
        logger.warning(f"Agent {agent_id} capacity limit reached: {active_claims}")
        raise HTTPException(
            status_code=403, 
            detail=f"Limit reached. Complete your {active_claims} active bookings before claiming more."
        )

    # 2. Atomic Transaction for Claiming
    try:
        # Use with_for_update to lock the row for the duration of this block
        booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
        
        if not booking:
            logger.error(f"Booking {booking_id} not found during claim.")
            raise HTTPException(status_code=404, detail="Booking not found.")
            
        if booking.agent_id:
            logger.info(f"Conflict: Booking {booking_id} already held by {booking.agent_id}")
            raise HTTPException(
                status_code=409, 
                detail=f"Conflict: Already claimed by Agent {booking.agent_id}"
            )
            
        if booking.escrow_status != EscrowStatus.VERIFIED:
            raise HTTPException(status_code=400, detail="Booking must be VERIFIED before claiming.")

        # 3. Perform Claim
        success = AgentBookingService.claim_booking(db, booking_id, agent_id)
        
        if success:
            # [22.4] WebSocket Broadcast to all Agents
            await ws_manager.broadcast_log(
                booking_id, 
                f"Claimed by {agent_id}", 
                "CLAIMED"
            )
            
            return {
                "status": "success", 
                "message": "Booking claimed. You have 15 minutes to fulfill.",
                "booking_id": booking_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to persist claim.")
            
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException): raise e
        logger.error(f"Concurrency error in claim: {e}")
        raise HTTPException(status_code=500, detail="System busy. Try again.")
