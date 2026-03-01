import logging
import asyncio
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import BookingRequest, BookingRequestPassenger, BookingQueue, User
from services.telegram_service import send_telegram_message, format_booking_alert

logger = logging.getLogger(__name__)

class BookingQueueService:
    def __init__(self, db: Session):
        self.db = db

    async def create_request(
        self,
        user_id: str,
        journey_data: Dict[str, Any],
        passengers: List[Dict[str, Any]],
        phone: str,
        email: str
    ) -> BookingRequest:
        """
        Creates a new booking request and adds it to the manual execution queue.
        Triggers a Telegram alert for the admin.
        """
        # 1. Create the BookingRequest
        new_request = BookingRequest(
            user_id=user_id,
            source_station=journey_data.get("source", "Unknown"),
            destination_station=journey_data.get("destination", "Unknown"),
            journey_date=datetime.strptime(journey_data.get("date", str(date.today())), "%Y-%m-%d").date(),
            train_number=journey_data.get("legs", [{}])[0].get("train_number", "00000"),
            train_name=journey_data.get("legs", [{}])[0].get("train_name", "Unknown"),
            class_type=journey_data.get("preferred_class", "AC_THREE_TIER"),
            status="PENDING",
            route_details=journey_data
        )
        self.db.add(new_request)
        self.db.flush()

        # 2. Add Passengers
        for p in passengers:
            pax = BookingRequestPassenger(
                booking_request_id=new_request.id,
                name=p.get("name"),
                age=p.get("age"),
                gender=p.get("gender"),
                berth_preference=p.get("preference")
            )
            self.db.add(pax)

        # 3. Add to Queue
        queue_entry = BookingQueue(
            booking_request_id=new_request.id,
            priority=5,
            status="WAITING"
        )
        self.db.add(queue_entry)
        
        self.db.commit()
        self.db.refresh(new_request)

        # 4. Trigger Telegram Alert
        try:
            alert_msg = format_booking_alert(
                booking_id=str(new_request.id),
                journey=journey_data,
                passengers=passengers,
                phone=phone,
                email=email
            )
            await send_telegram_message(alert_msg)
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")

        return new_request

    def get_pending_queue(self) -> List[BookingQueue]:
        return self.db.query(BookingQueue).filter(BookingQueue.status == "WAITING").all()

    async def update_status(self, request_id: str, status: str, admin_id: str, notes: str = None):
        """
        Updates the status of a booking request (e.g., SUCCESS, FAILED).
        This is called by the admin manually.
        """
        request = self.db.query(BookingRequest).filter(BookingRequest.id == request_id).first()
        if not request:
            return None
            
        request.status = status
        
        queue_entry = self.db.query(BookingQueue).filter(BookingQueue.booking_request_id == request_id).first()
        if queue_entry:
            queue_entry.status = "DONE" if status == "SUCCESS" else "FAILED"
            queue_entry.executed_by = admin_id
            queue_entry.execution_notes = notes
            queue_entry.completed_at = datetime.utcnow()
            
        self.db.commit()
        return request
