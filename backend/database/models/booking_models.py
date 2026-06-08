"""
SQLAlchemy models for booking system.
Covers: Bookings, Payments, Tickets, Refunds, Reviews
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, ForeignKey,
    Numeric, Date, CheckConstraint, Index, JSONB, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from database.infrastructure.session import Base


class Booking(Base):
    """Core booking record"""
    __tablename__ = "bookings"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Journey details
    train_number = Column(String(10), nullable=False, index=True)
    journey_date = Column(Date, nullable=False, index=True)
    source_station = Column(String(10), nullable=False)
    destination_station = Column(String(10), nullable=False)
    class_type = Column(String(5), nullable=False)  # 1A, 2A, 3A, SL

    # Passenger details
    passenger_name = Column(String(100), nullable=False)
    passenger_email = Column(String(100))
    passenger_phone = Column(String(20))
    passenger_gender = Column(String(10))
    passenger_dob = Column(Date)

    # Pricing breakdown
    base_fare = Column(Numeric(10, 2), nullable=False)
    taxes = Column(Numeric(10, 2), default=0)
    service_fee = Column(Numeric(10, 2), default=50)
    total_fare = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR")

    # Status tracking
    status = Column(String(30), nullable=False, default="PENDING_PAYMENT", index=True)

    # IRCTC integration
    pnr = Column(String(20), unique=True, nullable=True, index=True)
    ticket_number = Column(String(50), unique=True, nullable=True)
    seat_number = Column(String(10))
    coach_number = Column(String(10))

    # Cancellation
    cancellation_requested_at = Column(DateTime)
    cancellation_reason = Column(String(255))
    refund_amount = Column(Numeric(10, 2))

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    journey_completed_at = Column(DateTime, nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    payment = relationship("Payment", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    ticket = relationship("Ticket", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="booking", cascade="all, delete-orphan")
    review = relationship("BookingReview", back_populates="booking", uselist=False, cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint("journey_date >= CURRENT_DATE", name="valid_journey_date"),
        CheckConstraint("source_station != destination_station", name="valid_stations"),
        CheckConstraint("status IN ('PENDING_PAYMENT', 'PAYMENT_CONFIRMED', 'TICKET_CONFIRMED', 'COMPLETED', 'CANCELLED', 'REFUNDED')", name="valid_status"),
        CheckConstraint("class_type IN ('1A', '2A', '3A', 'SL')", name="valid_class"),
        Index("idx_bookings_user_id", "user_id"),
        Index("idx_bookings_status", "status"),
        Index("idx_bookings_journey_date", "journey_date"),
        Index("idx_bookings_train_number", "train_number"),
        Index("idx_bookings_created_at", "created_at"),
        Index("idx_bookings_pnr", "pnr"),
    )

    def __repr__(self):
        return f"<Booking {self.id} | {self.train_number} | {self.status}>"


class Payment(Base):
    """Payment transaction record"""
    __tablename__ = "payments"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Razorpay integration
    razorpay_order_id = Column(String(50), unique=True, nullable=True)
    razorpay_payment_id = Column(String(50), unique=True, nullable=True)
    razorpay_signature = Column(String(255))

    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR")
    payment_method = Column(String(50))  # card, upi, wallet, bank_transfer, netbanking
    status = Column(String(30), nullable=False, default="INITIATED", index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), index=True)
    confirmed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Error handling
    error_message = Column(String(500))
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    booking = relationship("Booking", back_populates="payment")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('INITIATED', 'PENDING', 'SUCCESS', 'FAILED', 'REFUNDED')", name="valid_payment_status"),
        CheckConstraint("retry_count >= 0", name="valid_retry_count"),
        Index("idx_payments_booking_id", "booking_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_razorpay_order", "razorpay_order_id"),
        Index("idx_payments_razorpay_payment", "razorpay_payment_id"),
        Index("idx_payments_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Payment {self.id} | {self.status} | ₹{self.amount}>"


class Ticket(Base):
    """Issued ticket record from IRCTC"""
    __tablename__ = "tickets"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Ticket details
    pnr = Column(String(20), unique=True, nullable=False, index=True)
    ticket_number = Column(String(50), unique=True, nullable=False)
    seat_number = Column(String(10))
    coach_number = Column(String(10))
    berth_type = Column(String(20))  # Upper, Middle, Lower, Sitting

    # IRCTC status
    irctc_status = Column(String(30), default="PENDING", index=True)
    chart_status_updated_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    booking = relationship("Booking", back_populates="ticket")

    # Constraints
    __table_args__ = (
        CheckConstraint("irctc_status IN ('PENDING', 'CONFIRMED', 'CHART_NOT_PREPARED', 'CANCELLED', 'WAITLIST')", name="valid_irctc_status"),
        Index("idx_tickets_booking_id", "booking_id"),
        Index("idx_tickets_pnr", "pnr"),
        Index("idx_tickets_irctc_status", "irctc_status"),
    )

    def __repr__(self):
        return f"<Ticket {self.pnr} | {self.irctc_status}>"


class Refund(Base):
    """Refund transaction record"""
    __tablename__ = "refunds"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)

    # Refund amount and status
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(30), nullable=False, default="INITIATED", index=True)

    # Razorpay refund tracking
    razorpay_refund_id = Column(String(50), unique=True, nullable=True)

    # Reason
    reason = Column(String(255))

    # Timestamps
    requested_at = Column(DateTime, server_default=func.now(), index=True)
    completed_at = Column(DateTime, nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    booking = relationship("Booking", back_populates="refunds")
    payment = relationship("Payment", back_populates="refunds")

    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED')", name="valid_refund_status"),
        Index("idx_refunds_booking_id", "booking_id"),
        Index("idx_refunds_status", "status"),
        Index("idx_refunds_requested_at", "requested_at"),
    )

    def __repr__(self):
        return f"<Refund {self.id} | {self.status} | ₹{self.amount}>"


class BookingReview(Base):
    """Post-journey booking review"""
    __tablename__ = "booking_reviews"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Overall rating
    overall_rating = Column(Integer)
    review_text = Column(Text)

    # Category ratings
    cleanliness_rating = Column(Integer)
    comfort_rating = Column(Integer)
    staff_rating = Column(Integer)
    food_rating = Column(Integer)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    booking = relationship("Booking", back_populates="review")

    # Constraints
    __table_args__ = (
        CheckConstraint("overall_rating >= 1 AND overall_rating <= 5", name="valid_overall_rating"),
        CheckConstraint("cleanliness_rating >= 1 AND cleanliness_rating <= 5", name="valid_cleanliness_rating"),
        CheckConstraint("comfort_rating >= 1 AND comfort_rating <= 5", name="valid_comfort_rating"),
        CheckConstraint("staff_rating >= 1 AND staff_rating <= 5", name="valid_staff_rating"),
        CheckConstraint("food_rating >= 1 AND food_rating <= 5", name="valid_food_rating"),
        Index("idx_reviews_booking_id", "booking_id"),
        Index("idx_reviews_user_id", "user_id"),
        Index("idx_reviews_overall_rating", "overall_rating"),
    )

    def __repr__(self):
        return f"<Review {self.id} | Rating: {self.overall_rating}★>"
