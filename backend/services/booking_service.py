from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging
from time import sleep

from backend.models import Booking, Route as RouteModel, Payment, User
# `Segment` model is optional (was removed/commented in models.py); import if present
try:
    from backend.models import Segment
except Exception:
    Segment = None
from backend.schemas import BookingResponseSchema
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)


class BookingService:
    """Handle booking creation and management."""

    MAX_RETRIES = 3

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
        """
        Create a booking record within a serializable transaction to prevent race conditions.
        Includes a retry mechanism for handling serialization failures.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                with self.db.begin_nested() as transaction:
                    # Set the transaction isolation level to SERIALIZABLE for this nested transaction
                    self.db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    
                    # Check if a booking already exists to provide a clearer error message
                    existing_booking = self.get_user_booking_for_route_date(user_id, route_id, travel_date)
                    if existing_booking:
                        logger.warning(f"User {user_id} already has a booking for route {route_id} on {travel_date}.")
                        return existing_booking

                    booking = Booking(
                        user_id=user_id,
                        route_id=route_id,
                        travel_date=travel_date,
                        payment_status="pending",
                        amount_paid=amount_paid,
                        booking_details=booking_details,
                    )
                    self.db.add(booking)
                    transaction.commit()
                
                self.db.refresh(booking)
                logger.info(f"Booking created (pending): {booking.id} on attempt {attempt + 1}")
                return booking

            except DBAPIError as e:
                # This specific error code indicates a serialization failure in PostgreSQL
                if e.orig.pgcode == '40001':
                    logger.warning(f"Serialization failure on attempt {attempt + 1}. Retrying...")
                    self.db.rollback()
                    sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Database error during booking creation: {e}")
                    self.db.rollback()
                    return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during booking creation: {e}")
                self.db.rollback()
                return None
        
        logger.error("Failed to create booking after multiple retries due to persistent serialization failures.")
        return None

    def hold_seat(
        self,
        user_id: str,
        route_id: str,
        travel_date: str,
        booking_details: Dict,
        amount_paid: float,
    ) -> Optional[Booking]:
        """
        Creates a pending booking (seat hold) for a user.
        This is a placeholder for actual seat reservation logic.
        """
        try:
            booking = Booking(
                user_id=user_id,
                route_id=route_id,
                travel_date=travel_date,
                payment_status="hold", # Use a specific status for held seats
                amount_paid=amount_paid,
                booking_details=booking_details,
            )
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            logger.info(f"Seat held for user {user_id}, route {route_id} on {travel_date}. Booking ID: {booking.id}")
            return booking
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to hold seat: {e}")
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
        This is called by the webhook and is designed to be idempotent.
        """
        try:
            # Find the payment record first
            payment = self.db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            if not payment:
                logger.warning(f"Payment record not found for order_id: {order_id}")
                return False

            # IDEMPOTENCY CHECK: If payment is already completed, do nothing.
            if payment.status == "completed":
                logger.warning(f"Payment for order_id: {order_id} has already been completed. Ignoring webhook event.")
                return True

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

    def get_booking_stats(self) -> Dict[str, Any]:
        """
        Calculates booking statistics, including total revenue and revenue per transport mode.
        Resolves N+1 queries by eager loading related data.
        """
        stats: Dict[str, Any] = {
            "total_bookings": 0,
            "completed_bookings": 0,
            "pending_bookings": 0,
            "total_revenue": 0.0,
            "revenue_by_mode": {},
            "top_routes_by_revenue": [], # Placeholder for future enhancement
        }

        # Fetch bookings with related Route and Segments eagerly loaded
        bookings = self.db.query(Booking).options(
            joinedload(Booking.route) # Eager load the Route associated with the Booking
        ).filter(Booking.payment_status == "completed").all() # Only consider completed bookings for revenue

        for booking in bookings:
            stats["total_bookings"] += 1 # This counts all bookings, including non-completed
            stats["completed_bookings"] += 1
            stats["total_revenue"] += booking.amount_paid

            if booking.route and booking.route.segments:
                # Assuming route.segments is a list of dicts from the JSON column
                # and each dict has a 'mode' key.
                # For simplicity, if a route is multi-modal, we attribute the full revenue
                # to the mode of its first segment for "Revenue per Mode" report.
                # A more accurate model would distribute revenue per segment.
                if booking.route.segments:
                    first_segment_mode = booking.route.segments[0].get("mode", "unknown")
                    stats["revenue_by_mode"].setdefault(first_segment_mode, 0.0)
                    stats["revenue_by_mode"][first_segment_mode] += booking.amount_paid
            
            # Increment pending bookings count separately if needed,
            # but current query only fetches completed for revenue.
            # To get full stats, would need to query all bookings then filter or two queries.

        # For pending bookings, fetch separately or adjust initial query
        stats["pending_bookings"] = self.db.query(Booking).filter(
            Booking.payment_status == "pending"
        ).count()
        stats["total_bookings"] = self.db.query(Booking).count()


        return stats
