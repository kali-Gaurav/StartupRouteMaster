import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import PaymentSession, Booking
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class SessionLockService:
    """
    Task 7: Session Lock & Navigation Guard.
    Manages payment session heartbeats and auto-cancellations.
    """
    
    # Task 10.1 & 10.6: Strict 10-minute expiry (600s) to sync with QR Code.
    # If heartbeat is lost for > 2 minutes, we consider them disconnected
    HARD_EXPIRY_SECONDS = 600 
    HEARTBEAT_TIMEOUT_SECONDS = 120 
    
    def __init__(self, db: Session):
        self.db = db

    def initialize_lock(self, session_code: str, user_id: str, booking_id: Optional[str] = None):
        """Called when user lands on the payment page."""
        cache_service.set(
            f"payment_session_lock:{session_code}", 
            {"user_id": user_id, "booking_id": booking_id, "status": "ACTIVE"}, 
            ttl_seconds=self.HARD_EXPIRY_SECONDS
        )
        # Initialize heartbeat tracker
        self.record_heartbeat(session_code)

    def record_heartbeat(self, session_code: str) -> bool:
        """Task 7.10: Heartbeat check to ensure user is still on the payment page."""
        lock_data = cache_service.get(f"payment_session_lock:{session_code}")
        if not lock_data:
            return False # Session already expired or invalid
            
        if lock_data.get("status") != "ACTIVE":
            return False

        # Reset the heartbeat TTL
        cache_service.set(
            f"payment_heartbeat:{session_code}", 
            datetime.utcnow().isoformat(), 
            ttl_seconds=self.HEARTBEAT_TIMEOUT_SECONDS
        )
        return True

    async def check_and_cancel_idle_sessions(self, session_code: str):
        """
        Task 7.7: Auto-cancel booking if user is idle.
        Can be run by a background worker or lazily checked.
        """
        lock_data = cache_service.get(f"payment_session_lock:{session_code}")
        if not lock_data:
            # Hard expiry reached
            await self._trigger_expiration(session_code)
            return True
            
        heartbeat = cache_service.get(f"payment_heartbeat:{session_code}")
        if not heartbeat:
            # Soft expiry reached (user closed tab without paying)
            logger.info(f"Session {session_code} lost heartbeat. Cancelling.")
            await self._trigger_expiration(session_code, lock_data)
            return True
            
        return False

    async def _trigger_expiration(self, session_code: str, lock_data: Dict[str, Any] = None):
        """Handles the expiration logic: DB update, WS Broadcast."""
        # 1. Update DB
        payment_session = self.db.query(PaymentSession).filter(PaymentSession.session_code == session_code).first()
        if payment_session and payment_session.status == "PENDING":
            payment_session.status = "EXPIRED"
            
            # Auto-cancel associated booking if it exists
            if lock_data and lock_data.get("booking_id"):
                booking = self.db.query(Booking).filter(Booking.id == lock_data["booking_id"]).first()
                if booking and booking.booking_status == "pending":
                    booking.booking_status = "cancelled"
                    booking.escrow_message = "Session abandoned by user."
            
            self.db.commit()

        # 2. Task 7.3: WebSocket-based "Session Expired" overlay
        # Trigger WS message to the client
        from api.websockets import manager
        if lock_data and lock_data.get("user_id"):
            await manager.send_personal_message(
                lock_data["user_id"],
                {"type": "SESSION_EXPIRED", "session_code": session_code, "message": "Payment session timed out."}
            )

        # 3. Clean up cache
        cache_service.delete(f"payment_session_lock:{session_code}")
        cache_service.delete(f"payment_heartbeat:{session_code}")
        
        logger.info(f"Session {session_code} marked as EXPIRED.")
