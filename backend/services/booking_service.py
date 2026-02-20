from sqlalchemy.orm import Session, joinedload
from datetime import datetime, date
from typing import Optional, Dict, List, Any
import logging
import asyncio

from backend.database.models import Booking, Route as RouteModel, Payment, User, PassengerDetails
from backend.schemas import BookingResponseSchema
from sqlalchemy.exc import DBAPIError
from backend.services.event_producer import publish_booking_created
from backend.database.config import Config
from backend.utils.generators import generate_pnr  # NEW: PNR generation
from backend.utils.validation import validate_date_string  # NEW: Validation

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
        passenger_details_list: Optional[List[Dict]] = None,  # NEW: Passenger details
    ) -> Optional[Booking]:
        """
        Create a booking record within a serializable transaction.
        
        Args:
            user_id: User ID
            route_id: Route ID (deprecated, supported for backward compatibility)
            travel_date: Travel date in YYYY-MM-DD format
            booking_details: Segments and route information
            amount_paid: Amount paid for booking
            passenger_details_list: List of passenger detail dicts [{"name": "...", "age": 30, ...}, ...]
            
        Returns:
            Booking object if successful, None otherwise
        """
        # Validate travel date
        travel_date_obj = validate_date_string(travel_date, allow_past=False)
        if not travel_date_obj:
            logger.error(f"Invalid travel date: {travel_date}")
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                with self.db.begin_nested() as transaction:
                    # Set the transaction isolation level to SERIALIZABLE for race condition prevention
                    self.db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    
                    # Generate unique PNR NEW
                    pnr_number = None
                    for retry in range(10):  # Try up to 10 times to generate unique PNR
                        candidate_pnr = generate_pnr()
                        existing = self.db.query(Booking).filter(
                            Booking.pnr_number == candidate_pnr
                        ).first()
                        if not existing:
                            pnr_number = candidate_pnr
                            break
                    
                    if not pnr_number:
                        logger.error("Failed to generate unique PNR after 10 attempts")
                        return None
                    
                    # Check if booking already exists (to prevent duplicates)
                    existing_booking = self.db.query(Booking).filter(
                        Booking.user_id == user_id,
                        Booking.travel_date == travel_date_obj,
                        Booking.booking_status.in_(["pending", "confirmed"])  # Don't recheck cancelled
                    ).first()
                    if existing_booking:
                        logger.warning(f"User {user_id} already has active booking for {travel_date}")
                        return existing_booking

                    # Create booking with new PNR NEW
                    booking = Booking(
                        pnr_number=pnr_number,  # NEW: Set PNR
                        user_id=user_id,
                        route_id=route_id,
                        travel_date=travel_date_obj,
                        booking_status="pending",  # NEW: Use booking_status instead of payment_status
                        amount_paid=amount_paid,
                        booking_details=booking_details,
                    )
                    self.db.add(booking)
                    self.db.flush()  # Flush to get booking.id
                    
                    # Add passenger details NEW
                    if passenger_details_list:
                        for pax_detail in passenger_details_list:
                            try:
                                passenger = PassengerDetails(
                                    booking_id=booking.id,
                                    full_name=pax_detail.get("full_name", ""),
                                    age=pax_detail.get("age", 0),
                                    gender=pax_detail.get("gender", "M"),
                                    phone_number=pax_detail.get("phone_number"),
                                    email=pax_detail.get("email"),
                                    document_type=pax_detail.get("document_type"),
                                    document_number=pax_detail.get("document_number"),
                                    concession_type=pax_detail.get("concession_type"),
                                    concession_discount=pax_detail.get("concession_discount", 0.0),
                                    meal_preference=pax_detail.get("meal_preference"),
                                )
                                self.db.add(passenger)
                            except Exception as e:
                                logger.warning(f"Failed to add passenger details: {e}")
                    
                    transaction.commit()
                
                self.db.refresh(booking)
                logger.info(f"Booking created (pending): {booking.pnr_number} on attempt {attempt + 1}")

                # Fire-and-forget: publish booking event for analytics
                if Config.KAFKA_ENABLE_EVENTS:
                    try:
                        segments = booking_details.get('segments', [])
                        asyncio.create_task(
                            publish_booking_created(
                                user_id=user_id,
                                route_id=route_id,
                                total_cost=amount_paid,
                                segments=segments,
                                booking_reference=booking.pnr_number  # NEW: Use PNR as reference
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Failed to publish booking event: {e}")

                return booking

            except DBAPIError as e:
                # Serialization failure (PostgreSQL error code 40001)
                if hasattr(e.orig, 'pgcode') and e.orig.pgcode == '40001':
                    logger.warning(f"Serialization failure on attempt {attempt + 1}. Retrying...")
                    self.db.rollback()
                    sleep(0.5 * (2 ** attempt))  # Exponential backoff: 0.5s, 1s, 2s
                else:
                    logger.error(f"Database error during booking creation: {e}")
                    self.db.rollback()
                    return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during booking creation: {e}")
                self.db.rollback()
                return None
        
        logger.error("Failed to create booking after multiple retries due to serialization failures.")
        return None

    def confirm_booking(self, booking_id: str) -> bool:
        """
        Confirm a pending booking (after payment is successful).
        
        Args:
            booking_id: Booking ID to confirm
            
        Returns:
            True if confirmed, False otherwise
        """
        try:
            booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                logger.error(f"Booking not found: {booking_id}")
                return False
            
            # Validate state transition NEW
            if not booking.validate_status_transition("confirmed"):
                logger.error(f"Cannot transition from {booking.booking_status} to confirmed")
                return False
            
            booking.booking_status = "confirmed"
            self.db.commit()
            logger.info(f"Booking confirmed: {booking.pnr_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to confirm booking: {e}")
            self.db.rollback()
            return False

    def cancel_booking(self, booking_id: str, reason: str = "") -> bool:
        """
        Cancel a booking.
        
        Args:
            booking_id: Booking ID to cancel
            reason: Reason for cancellation
            
        Returns:
            True if cancelled, False otherwise
        """
        try:
            booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                logger.error(f"Booking not found: {booking_id}")
                return False
            
            # Validate state transition NEW
            if not booking.validate_status_transition("cancelled"):
                logger.error(f"Cannot cancel booking in {booking.booking_status} state")
                return False
            
            booking.booking_status = "cancelled"
            self.db.commit()
            logger.info(f"Booking cancelled: {booking.pnr_number} ({reason})")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel booking: {e}")
            self.db.rollback()
            return False

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
            travel_date_obj = validate_date_string(travel_date, allow_past=False)
            if not travel_date_obj:
                logger.error(f"Invalid travel date for seat hold: {travel_date}")
                return None
            
            booking = Booking(
                pnr_number=generate_pnr(),  # NEW: Always generate PNR
                user_id=user_id,
                route_id=route_id,
                travel_date=travel_date_obj,
                booking_status="pending",  # NEW: Use booking_status
                amount_paid=amount_paid,
                booking_details=booking_details,
            )
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            logger.info(f"Seat held. PNR: {booking.pnr_number}")
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
            logger.info(f"Pending payment record created for booking {booking.pnr_number}")
            return payment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create pending payment: {e}")
            return None

    def get_booking_by_pnr(self, pnr: str) -> Optional[Booking]:
        """NEW: Get booking by PNR number."""
        try:
            booking = self.db.query(Booking).filter(
                Booking.pnr_number == pnr
            ).first()
            return booking
        except Exception as e:
            logger.error(f"Failed to fetch booking by PNR: {e}")
            return None

    def get_user_bookings(self, user_id: str) -> List[Booking]:
        """Get all bookings for a user."""
        try:
            bookings = self.db.query(Booking).filter(
                Booking.user_id == user_id
            ).order_by(Booking.created_at.desc()).all()
            return bookings
        except Exception as e:
            logger.error(f"Failed to fetch user bookings: {e}")
            return []

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
