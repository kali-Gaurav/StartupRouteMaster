import logging
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date

from database.models import Booking, BookingStatus, EscrowStatus, User
from services.booking_service import BookingService
from services.booking_queue_service import BookingQueueService
from services.agent_booking_service import AgentBookingService
from providers.gateway import provider_gateway

logger = logging.getLogger("booking-orchestrator")

class BookingOrchestrator:
    """
    [Task 4.1] Agentic Booking Orchestrator.
    Dynamically decides between automated (API) and manual (Agent) fulfillment.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.auto_service = BookingService(db)
        self.queue_service = BookingQueueService(db)
        self.agent_service = AgentBookingService()

    async def initiate_booking(
        self,
        user: User,
        journey_data: Dict[str, Any],
        passengers: List[Dict[str, Any]],
        preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Decision logic for the booking path.
        """
        is_tatkal = journey_data.get("quota") == "TQ"
        is_emergency = (preferences or {}).get("persona") == "emergency"
        
        user_id = str(user.id)
        user_phone = str(user.phone_number or "9999999999")
        user_email = str(user.email or "guest@routemaster.ai")

        # AGENTIC DECISION: Route to Agent Queue for high-complexity/high-risk tasks
        if is_tatkal or is_emergency:
            logger.info(f"Routing to MANUAL AGENT for {user_id} (Tatkal/Emergency)")
            request = await self.queue_service.create_request(
                user_id=user_id,
                journey_data=journey_data,
                passengers=passengers,
                phone=user_phone,
                email=user_email
            )
            return {
                "booking_id": str(request.id),
                "path": "MANUAL_AGENT",
                "status": "QUEUED",
                "message": "Your booking is in the priority agent queue for fulfillment."
            }

        # DEFAULT: Try Automated API Path
        logger.info(f"Routing to AUTOMATED API for {user.id}")
        amount_paid = journey_data.get("total_price", 0.0)
        
        # Create the local DB record first (Pending)
        booking = self.auto_service.create_booking(
            user_id=user_id,
            route_id=journey_data.get("route_id", "generated"),
            travel_date=journey_data.get("date", str(date.today())),
            booking_details=journey_data,
            amount_paid=amount_paid,
            passenger_details_list=passengers
        )
        
        if not booking:
            return {"error": "Failed to initialize booking record."}

        return {
            "booking_id": booking.id,
            "pnr": booking.pnr_number,
            "path": "AUTOMATED_API",
            "status": "PENDING_PAYMENT",
            "message": "Awaiting payment to finalize automated booking."
        }
