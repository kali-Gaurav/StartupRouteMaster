from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import Optional, Dict, List
import logging

from backend.models import Booking, Route as RouteModel, Payment, User
from backend.schemas import BookingResponseSchema

logger = logging.getLogger(__name__)


class BookingService:
    """Handle booking creation and management."""

    def __init__(self, db: Session):
        self.db = db

    def create_booking(
        self,
        user_id: str,
        route_id: str,
        travel_date: str,
        booking_details: Dict,
        amount_paid: float,
    ) -> Optional[Booking]:
        """Create a booking record with a 'pending' status."""
        try:
            booking = Booking(
                user_id=user_id,
                route_id=route_id,
                travel_date=travel_date,
                payment_status="pending",
                amount_paid=amount_paid,
                booking_details=booking_details,
            )
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            logger.info(f"Booking created (pending): {booking.id}")
            return booking
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create booking: {e}")
            return None

    def create_pending_payment(
        self, booking: Booking, razorpay_order_id: str
    ) -> Optional[Payment]:
        """Create a pending payment record linked to a booking."""
        try:
            payment = Payment(
                booking_id=booking.id,
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=booking.amount_paid,
            )
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
            logger.info(f"Pending payment record created for booking {booking.id}")
            return payment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create pending payment: {e}")
            return None

    def confirm_booking_payment(
        self, order_id: str, payment_id: str, payment_status: str
    ) -> bool:
        """
        Find booking by razorpay_order_id and update it with payment details.
        This is called by the webhook.
        """
        try:
            # Find the payment record first
            payment = self.db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            if not payment:
                logger.warning(f"Payment record not found for order_id: {order_id}")
                return False

            # Update the payment record itself
            payment.razorpay_payment_id = payment_id
            payment.status = payment_status
            
            # Now find the associated booking
            booking = self.db.query(Booking).filter(Booking.id == payment.booking_id).first()
            if not booking:
                logger.error(f"CRITICAL: Booking not found for payment {payment.id}, but payment was made!")
                return False

            booking.payment_status = payment_status
            self.db.commit()
            logger.info(f"Booking {booking.id} payment confirmed with status '{payment_status}'")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update booking payment status: {e}")
            return False

    def get_booking(self, booking_id: str, user: User) -> Optional[Booking]:
        """Get a single booking for a user."""
        try:
            booking = self.db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
            return booking
        except Exception as e:
            logger.error(f"Failed to get booking: {e}")
            return None

    def get_bookings_by_user(self, user: User) -> List[Booking]:
        """Get all bookings for a specific user, eagerly loading route details."""
        try:
            bookings = (
                self.db.query(Booking)
                .options(joinedload(Booking.route))
                .filter(Booking.user_id == user.id)
                .order_by(Booking.created_at.desc())
                .all()
            )
            return bookings
        except Exception as e:
            logger.error(f"Failed to get bookings for user {user.id}: {e}")
            return []

    def get_user_booking_for_route_date(
        self, user_id: str, route_id: str, travel_date: str
    ) -> Optional[Booking]:
        """Retrieve a booking for a specific user, route, and travel date."""
        try:
            return self.db.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.route_id == route_id,
                Booking.travel_date == travel_date
            ).first()
        except Exception as e:
            logger.error(f"Failed to get booking for user {user_id}, route {route_id}, date {travel_date}: {e}")
            return None

    def is_booking_payment_completed(
        self, user_id: str, route_id: str, travel_date: str
    ) -> bool:
        """Check if a booking's payment status is 'completed' for a user, route, and date."""
        try:
            booking = self.get_user_booking_for_route_date(user_id, route_id, travel_date)
            return booking is not None and booking.payment_status == "completed"
        except Exception as e:
            logger.error(f"Failed to check booking payment status: {e}")
            return False
