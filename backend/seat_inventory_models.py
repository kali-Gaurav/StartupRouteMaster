"""
Seat Inventory & Booking Engine - Core Models

Implements IRCTC-grade seat inventory management with:
- Quota-based allocation (General, Tatkal, Ladies, Senior, etc.)
- Segment-based inventory (not whole journey)
- Waitlist and RAC management
- High-contention locking for Tatkal
- Distributed booking transactions
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey,
    Text, JSON, CheckConstraint, UniqueConstraint, Index, Date, Time,
    Enum, Numeric
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from backend.database import Base


# ==============================================================================
# ENUMS
# ==============================================================================

class QuotaType(enum.Enum):
    """Seat quota types (IRCTC standard)"""
    GENERAL = "general"
    TATKAL = "tatkal"
    LADIES = "ladies"
    SENIOR_CITIZEN = "senior_citizen"
    DEFENCE = "defence"
    FOREIGN_TOURIST = "foreign_tourist"
    DUTY_PASS = "duty_pass"
    PARLIAMENT = "parliament"
    HANDICAPPED = "handicapped"
    YUVA = "yuva"

class BookingStatus(enum.Enum):
    """Booking status"""
    CONFIRMED = "confirmed"
    RAC = "rac"  # Reservation Against Cancellation
    WAITLIST = "waitlist"
    CANCELLED = "cancelled"

class SeatType(enum.Enum):
    """Seat types"""
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"
    SIDE_LOWER = "side_lower"
    SIDE_UPPER = "side_upper"
    WINDOW = "window"
    AISLE = "aisle"

class CoachClass(enum.Enum):
    """Coach classes"""
    SL = "sl"      # Sleeper
    AC3 = "ac3"    # AC 3-Tier
    AC2 = "ac2"    # AC 2-Tier
    AC1 = "ac1"    # AC 1st Class
    CC = "cc"      # Chair Car
    EC = "ec"      # Executive Chair Car
    EA = "ea"      # Anubhuti

# ==============================================================================
# CORE SEAT INVENTORY MODELS
# ==============================================================================

class Coach(Base):
    """Coach details for each train"""
    __tablename__ = "coaches"
    __table_args__ = (
        UniqueConstraint('train_id', 'coach_number', name='uq_train_coach'),
        Index("idx_coaches_train_id", "train_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    train_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    coach_number = Column(String(10), nullable=False)  # e.g., "S1", "A1"
    coach_class = Column(Enum(CoachClass), nullable=False)
    total_seats = Column(Integer, nullable=False)
    base_fare_multiplier = Column(Float, default=1.0, nullable=False)

    # Relationships
    train = relationship("Trip", back_populates="coaches")
    seats = relationship("Seat", back_populates="coach", cascade="all, delete-orphan")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Coach(train_id={self.train_id}, coach={self.coach_number}, class={self.coach_class.value})>"


class Seat(Base):
    """Individual seat in a coach"""
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint('coach_id', 'seat_number', name='uq_coach_seat'),
        Index("idx_seats_coach_id", "coach_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    coach_id = Column(String(36), ForeignKey("coaches.id"), nullable=False, index=True)
    seat_number = Column(String(10), nullable=False)  # e.g., "001", "01A"
    seat_type = Column(Enum(SeatType), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_preferred = Column(Boolean, default=False, nullable=False)  # Window, side preferences

    # Relationships
    coach = relationship("Coach", back_populates="seats")
    inventory_items = relationship("SeatInventory", back_populates="seat", cascade="all, delete-orphan")

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Seat(coach={self.coach_id}, seat={self.seat_number}, type={self.seat_type.value})>"


class SeatInventory(Base):
    """Seat inventory for specific train segments and dates"""
    __tablename__ = "seat_inventory"
    __table_args__ = (
        UniqueConstraint('trip_id', 'segment_from_stop_id', 'segment_to_stop_id', 'date', 'quota_type', name='uq_inventory_segment'),
        Index("idx_seat_inventory_trip_date", "trip_id", "date"),
        Index("idx_seat_inventory_segment", "segment_from_stop_id", "segment_to_stop_id"),
        Index("idx_seat_inventory_quota", "quota_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    segment_from_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    segment_to_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    quota_type = Column(Enum(QuotaType), nullable=False, index=True)

    # Availability counts
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    booked_seats = Column(Integer, default=0, nullable=False)
    blocked_seats = Column(Integer, default=0, nullable=False)  # For Tatkal processing

    # Waitlist management
    current_waitlist_position = Column(Integer, default=0, nullable=False)
    rac_count = Column(Integer, default=0, nullable=False)

    # Relationships
    trip = relationship("Trip")
    segment_from_stop = relationship("Stop", foreign_keys=[segment_from_stop_id])
    segment_to_stop = relationship("Stop", foreign_keys=[segment_to_stop_id])
    seat = relationship("Seat", back_populates="inventory_items", uselist=False)

    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SeatInventory(trip={self.trip_id}, segment={self.segment_from_stop_id}-{self.segment_to_stop_id}, quota={self.quota_type.value}, available={self.available_seats})>"


class QuotaInventory(Base):
    """Quota-specific inventory allocation"""
    __tablename__ = "quota_inventory"
    __table_args__ = (
        UniqueConstraint('inventory_id', 'quota_type', name='uq_quota_inventory'),
        Index("idx_quota_inventory_inventory", "inventory_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_id = Column(String(36), ForeignKey("seat_inventory.id"), nullable=False, index=True)
    quota_type = Column(Enum(QuotaType), nullable=False)
    allocated_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    max_allocation = Column(Integer, nullable=False)  # Quota limit

    # Relationships
    inventory = relationship("SeatInventory", backref="quota_allocations")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WaitlistQueue(Base):
    """Waitlist queue for bookings"""
    __tablename__ = "waitlist_queue"
    __table_args__ = (
        Index("idx_waitlist_queue_inventory", "inventory_id"),
        Index("idx_waitlist_queue_position", "waitlist_position"),
        Index("idx_waitlist_queue_user", "user_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_id = Column(String(36), ForeignKey("seat_inventory.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    waitlist_position = Column(Integer, nullable=False)
    booking_request_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Booking details
    passengers_json = Column(JSON, nullable=False)  # Passenger details
    preferences_json = Column(JSON, nullable=True)  # Seat preferences

    # Status
    status = Column(Enum(BookingStatus), default=BookingStatus.WAITLIST, nullable=False)
    promoted_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)

    # Relationships
    inventory = relationship("SeatInventory", backref="waitlist_entries")
    user = relationship("User", backref="waitlist_entries")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PNRRecord(Base):
    """PNR (Passenger Name Record) for confirmed bookings"""
    __tablename__ = "pnr_records"
    __table_args__ = (
        UniqueConstraint('pnr_number', name='uq_pnr_number'),
        Index("idx_pnr_records_pnr", "pnr_number"),
        Index("idx_pnr_records_user", "user_id"),
        Index("idx_pnr_records_date", "travel_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_number = Column(String(10), unique=True, nullable=False, index=True)  # 10-digit PNR
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)

    # Booking details
    total_passengers = Column(Integer, nullable=False)
    total_fare = Column(Numeric(10, 2), nullable=False)
    booking_status = Column(Enum(BookingStatus), nullable=False)

    # Payment
    payment_status = Column(String(20), default="pending", nullable=False)
    payment_id = Column(String(100), nullable=True)

    # Segments (JSON array of segment details)
    segments_json = Column(JSON, nullable=False)

    # Cancellation
    cancelled_at = Column(DateTime, nullable=True)
    refund_amount = Column(Numeric(10, 2), nullable=True)

    # Relationships
    user = relationship("User", backref="pnr_records")
    passenger_details = relationship("PassengerDetail", back_populates="pnr_record", cascade="all, delete-orphan")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PassengerDetail(Base):
    """Individual passenger details within a PNR"""
    __tablename__ = "passenger_details"
    __table_args__ = (
        Index("idx_passenger_details_pnr", "pnr_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_id = Column(String(36), ForeignKey("pnr_records.id"), nullable=False, index=True)

    # Personal details
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    berth_preference = Column(Enum(SeatType), nullable=True)

    # Allocation details
    coach_number = Column(String(10), nullable=True)
    seat_number = Column(String(10), nullable=True)
    seat_type = Column(Enum(SeatType), nullable=True)
    status = Column(Enum(BookingStatus), nullable=False)

    # Relationships
    pnr_record = relationship("PNRRecord", back_populates="passenger_details")

    created_at = Column(DateTime, default=datetime.utcnow)


class BookingLock(Base):
    """Distributed locks for seat booking (Tatkal protection)"""
    __tablename__ = "booking_locks"
    __table_args__ = (
        UniqueConstraint('lock_key', name='uq_lock_key'),
        Index("idx_booking_locks_key", "lock_key"),
        Index("idx_booking_locks_expiry", "expires_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lock_key = Column(String(200), unique=True, nullable=False, index=True)  # e.g., "seat:123:2024-01-01:S1-001"
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(100), nullable=False)  # For cleanup

    # Lock details
    acquired_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    ttl_seconds = Column(Integer, default=60, nullable=False)  # Default 60 seconds

    # Metadata
    lock_type = Column(String(20), default="seat", nullable=False)  # seat, coach, train
    resource_id = Column(String(100), nullable=False)  # seat/coach/train identifier

    created_at = Column(DateTime, default=datetime.utcnow)

    def is_expired(self) -> bool:
        """Check if lock has expired"""
        return datetime.utcnow() > self.expires_at

    def extend_lock(self, additional_seconds: int = 30):
        """Extend lock expiry"""
        self.expires_at = datetime.utcnow() + timedelta(seconds=additional_seconds)
        self.ttl_seconds += additional_seconds