import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Booking, User

logger = logging.getLogger(__name__)

class RefundService:
    """
    Task 6: Refund Queue State Machine
    """
    
    # Task 6.1: State Machine constants
    STATE_PENDING = "REFUND_PENDING"
    STATE_REQUIRES_APPROVAL = "REQUIRES_APPROVAL" # Task 6.4
    STATE_INITIATED = "REFUND_INITIATED"
    STATE_SUCCESS = "REFUND_SUCCESS"
    STATE_FAILED = "REFUND_FAILED"

    def __init__(self, db: Session):
        self.db = db

    def _notify_slack(self, message: str):
        """Task 6.9: Slack bot alerts for failed refunds."""
        logger.warning(f"SLACK REFUND ALERT: {message}")

    def create_refund_request(self, booking_id: str, reason: str, amount: float, is_partial: bool = False, cancellation_charge: float = 0.0) -> Dict[str, Any]:
        """
        Creates a refund request in the queue.
        Supports Task 6.2 (Sold out trigger) and 6.5 (Partial refund).
        """
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return {"success": False, "message": "Booking not found"}

        # Task 6.5: Partial refund logic
        final_amount = amount
        if is_partial and cancellation_charge > 0:
            final_amount = max(0, amount - cancellation_charge)

        # Task 6.4: Manual approval workflow for high-value refunds (>₹5000)
        initial_status = self.STATE_PENDING
        if final_amount > 5000.0:
            initial_status = self.STATE_REQUIRES_APPROVAL
            self._notify_slack(f"High-value refund requires manual approval: Booking {booking_id}, Amount {final_amount}")

        # In a real app, this goes to a dedicated Refund table. Using booking details for demo.
        refund_data = {
            "amount": final_amount,
            "status": initial_status,
            "reason": reason,
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }
        
        booking.booking_details = booking.booking_details or {}
        booking.booking_details["refund_info"] = refund_data
        
        # Auto-cancel booking if it was sold out (Task 6.2)
        if reason == "IRCTC_SOLD_OUT":
            booking.booking_status = "cancelled"
            
        self.db.commit()
        return {"success": True, "refund_status": initial_status, "amount": final_amount}

    def process_refund(self, booking_id: str, target_vpa: str = None) -> Dict[str, Any]:
        """
        Moves a refund from PENDING to INITIATED to SUCCESS.
        """
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking or "refund_info" not in (booking.booking_details or {}):
            return {"success": False, "message": "No refund request found"}
            
        refund_info = booking.booking_details["refund_info"]
        
        if refund_info["status"] == self.STATE_REQUIRES_APPROVAL:
            return {"success": False, "message": "Refund requires admin approval first."}
            
        if refund_info["status"] in [self.STATE_SUCCESS, self.STATE_INITIATED]:
            return {"success": False, "message": f"Refund already in state {refund_info['status']}"}

        # Task 6.3: User VPA verification before refund
        user = self.db.query(User).filter(User.id == booking.user_id).first()
        vpa_to_use = target_vpa # Since we don't have a VPA field on User in this schema
        
        from sqlalchemy.orm.attributes import flag_modified
        
        if not vpa_to_use:
            # Task 6.10: Auto-retry logic preparation
            refund_info["retry_count"] = refund_info.get("retry_count", 0) + 1
            refund_info["status"] = self.STATE_FAILED
            
            booking.booking_details["refund_info"] = refund_info
            flag_modified(booking, "booking_details")
            self.db.commit()
            
            self._notify_slack(f"Refund failed for Booking {booking_id}: No VPA found. Retry count: {refund_info['retry_count']}")
            return {"success": False, "message": "VPA verification failed"}

        # Simulate Bank API Call
        refund_info["status"] = self.STATE_INITIATED
        booking.booking_details["refund_info"] = refund_info
        flag_modified(booking, "booking_details")
        self.db.commit()
        
        # Task 6.6: Refund receipt generation
        receipt = {
            "receipt_id": f"REF-{booking_id[:8]}",
            "amount": refund_info["amount"],
            "vpa": vpa_to_use,
            "date": datetime.utcnow().isoformat()
        }
        
        # Simulate success
        refund_info["status"] = self.STATE_SUCCESS
        refund_info["receipt"] = receipt
        
        # Update original booking details
        booking.booking_details["refund_info"] = refund_info
        flag_modified(booking, "booking_details")
        self.db.commit()

        return {"success": True, "message": "Refund processed successfully", "receipt": receipt}

    def admin_approve_refund(self, booking_id: str) -> Dict[str, Any]:
        """Admin endpoint to approve high-value refunds."""
        booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking or "refund_info" not in (booking.booking_details or {}):
            return {"success": False, "message": "No refund request found"}
            
        from sqlalchemy.orm.attributes import flag_modified
        refund_info = booking.booking_details["refund_info"]
        if refund_info["status"] == self.STATE_REQUIRES_APPROVAL:
            refund_info["status"] = self.STATE_PENDING
            booking.booking_details["refund_info"] = refund_info
            flag_modified(booking, "booking_details")
            self.db.commit()
            return {"success": True, "message": "Refund approved and queued for processing"}
            
        return {"success": False, "message": "Refund does not require approval"}

    def process_bulk_refunds(self) -> Dict[str, Any]:
        """Task 6.7: Bulk refund processing via Bank API/CSV."""
        # Find all pending refunds
        # (In a real app, query the Refund table. Here we scan bookings with refund_info)
        bookings = self.db.query(Booking).all()
        processed = 0
        failed = 0
        
        for b in bookings:
            details = b.booking_details or {}
            if "refund_info" in details:
                if details["refund_info"]["status"] == self.STATE_PENDING:
                    res = self.process_refund(str(b.id))
                    if res["success"]: processed += 1
                    else: failed += 1
                    
        return {"success": True, "processed": processed, "failed": failed}
