"""
Booking Service - Core business logic for booking management.
Handles: create booking, confirm payment, list bookings, cancel, refund
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models.booking_models import (
    Booking, Payment, Ticket, Refund
)

logger = logging.getLogger(__name__)


class BookingService:
    """Service for booking operations"""

    @staticmethod
    def create_booking(
        db: Session,
        user_id: UUID,
        train_number: str,
        journey_date: str,
        source_station: str,
        destination_station: str,
        class_type: str,
        passenger_name: str,
        passenger_email: str,
        passenger_phone: str,
        passenger_gender: str,
        passenger_dob: Optional[str],
        base_fare: Decimal,
        taxes: Decimal = Decimal("0"),
        service_fee: Decimal = Decimal("50"),
    ) -> Booking:
        """Create new booking - status PENDING_PAYMENT"""
        try:
            total_fare = base_fare + taxes + service_fee
            booking = Booking(
                user_id=user_id,
                train_number=train_number,
                journey_date=journey_date,
                source_station=source_station,
                destination_station=destination_station,
                class_type=class_type,
                passenger_name=passenger_name,
                passenger_email=passenger_email,
                passenger_phone=passenger_phone,
                passenger_gender=passenger_gender,
                passenger_dob=passenger_dob,
                base_fare=base_fare,
                taxes=taxes,
                service_fee=service_fee,
                total_fare=total_fare,
                status="PENDING_PAYMENT",
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)
            logger.info(f"Booking created: {booking.id}")
            return booking
        except Exception as e:
            db.rollback()
            logger.error(f"Error: {str(e)}")
            raise

    @staticmethod
    def get_booking(db: Session, booking_id: UUID) -> Optional[Booking]:
        """Fetch booking by ID"""
        return db.query(Booking).filter(Booking.id == booking_id).first()

    @staticmethod
    def get_user_bookings(
        db: Session,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple:
        """Fetch user bookings"""
        query = db.query(Booking).filter(Booking.user_id == user_id)
        if status:
            query = query.filter(Booking.status == status)
        total = query.count()
        bookings = query.order_by(desc(Booking.created_at)).limit(limit).offset(offset).all()
        return bookings, total

    @staticmethod
    def update_booking_status(
        db: Session,
        booking_id: UUID,
        new_status: str,
        additional_data: Optional[Dict] = None,
    ) -> Booking:
        """Update booking status"""
        try:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                raise ValueError(f"Booking not found")
            booking.status = new_status
            booking.updated_at = datetime.utcnow()
            if additional_data:
                if "pnr" in additional_data:
                    booking.pnr = additional_data["pnr"]
                if "ticket_number" in additional_data:
                    booking.ticket_number = additional_data["ticket_number"]
            db.commit()
            db.refresh(booking)
            logger.info(f"Booking {booking_id} status: {new_status}")
            return booking
        except Exception as e:
            db.rollback()
            logger.error(f"Error: {str(e)}")
            raise


class PaymentService:
    """Service for payment operations"""

    @staticmethod
    def create_payment_record(
        db: Session,
        booking_id: UUID,
        amount: Decimal,
        razorpay_order_id: str,
    ) -> Payment:
        """Create payment record"""
        try:
            payment = Payment(
                booking_id=booking_id,
                amount=amount,
                razorpay_order_id=razorpay_order_id,
                status="INITIATED",
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            logger.info(f"Payment created: {payment.id}")
            return payment
        except Exception as e:
            db.rollback()
            logger.error(f"Error: {str(e)}")
            raise

    @staticmethod
    def confirm_payment(
        db: Session,
        payment_id: UUID,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Payment:
        """Mark payment as confirmed"""
        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise ValueError(f"Payment not found")
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = "SUCCESS"
            payment.confirmed_at = datetime.utcnow()
            booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
            if booking:
                booking.status = "PAYMENT_CONFIRMED"
            db.commit()
            db.refresh(payment)
            logger.info(f"Payment confirmed: {payment_id}")
            return payment
        except Exception as e:
            db.rollback()
            logger.error(f"Error: {str(e)}")
            raise

    @staticmethod
    def get_payment_by_booking(db: Session, booking_id: UUID) -> Optional[Payment]:
        """Fetch payment by booking"""
        return db.query(Payment).filter(Payment.booking_id == booking_id).first()


class RefundService:
    """Service for refund operations"""

    @staticmethod
    def create_refund(
        db: Session,
        booking_id: UUID,
        payment_id: UUID,
        amount: Decimal,
        reason: str,
    ) -> Refund:
        """Create refund record"""
        try:
            refund = Refund(
                booking_id=booking_id,
                payment_id=payment_id,
                amount=amount,
                reason=reason,
                status="INITIATED",
            )
            db.add(refund)
            db.commit()
            db.refresh(refund)
            logger.info(f"Refund created: {refund.id}")
            return refund
        except Exception as e:
            db.rollback()
            logger.error(f"Error: {str(e)}")
            raise
