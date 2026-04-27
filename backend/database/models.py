import hashlib
import json

from database.base import AuditMixin,TimestampMixin, Base, UserBase, TransitBase

from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, DateTime, Boolean, ForeignKey, JSON, Text, 
    LargeBinary, CheckConstraint, UniqueConstraint, Date, Index, Time, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, declarative_base, backref, Session, Mapped, mapped_column, synonym
from typing import Optional, Dict, List, Any
from datetime import datetime, date, time
import uuid
import enum
import logging
import sys
from pathlib import Path

# [Task 117.9] Link backend module base index
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.append(str(_root))

# from database.base import Base, UserBase, TransitBase  <- This was changed to import Base directly
# from database.base import UserBase, TransitBase # This was removed to avoid circularity

logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================

from core.data_structures import QuotaType, BookingStatus, EscrowStatus, Persona, AllocationStatus, Route

class CoachClass(enum.Enum):
    SL = "sl"
    AC3 = "ac3"
    AC2 = "ac2"
    AC1 = "ac1"
    CC = "cc"
    EC = "ec"

class BankTransaction(UserBase):
    __tablename__ = "bank_transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    utr_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="UNCLAIMED") # UNCLAIMED, MATCHED, PROCESSING, VOIDED_BY_BAILIFF
    sender_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

class UserAlert(UserBase):
    __tablename__ = "user_alerts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])

# ==============================================================================
# USER STORE MODELS (user_store.db)
# ==============================================================================

class User(UserBase, TimestampMixin, AuditMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    supabase_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Task 3.1: Telegram Integration
    telegram_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    telegram_link_token: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    telegram_link_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Task 35: Credential Vault
    encrypted_irctc_creds: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    creds_iv: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    opt_in_persistent_creds: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # [Task 42.A] Token Economy
    credit_balance: Mapped[int] = mapped_column(Integer, default=0)
    bonus_credit_balance: Mapped[int] = mapped_column(Integer, default=0)
    total_lifetime_credits: Mapped[int] = mapped_column(Integer, default=0)
    
    # [Task 43.A] Referral & Karma Engine
    referral_code: Mapped[Optional[str]] = mapped_column(String(12), unique=True, index=True, nullable=True)
    referred_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    karma_score: Mapped[int] = mapped_column(Integer, default=0)
    referral_status: Mapped[str] = mapped_column(String(20), default="INITIATED") # INITIATED, CONVERTED
    last_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # [45.1]

    bookings = relationship("Booking", back_populates="user", foreign_keys="[Booking.user_id]")
    profile = relationship("Profile", back_populates="user", uselist=False)
    reviews = relationship("Review", back_populates="user")
    commission_tracks = relationship("CommissionTracking", back_populates="user")
    unlocked_routes = relationship("UnlockedRoute", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    route_search_logs = relationship("RouteSearchLog", back_populates="user")
    ai_preferences = relationship("UserAIPreference", back_populates="user", uselist=False)
    ai_intents = relationship("AIIntentLog", back_populates="user")
    chat_history = relationship("PersistentChatMessage", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    emergency_contacts = relationship("EmergencyContact", back_populates="user", cascade="all, delete-orphan")
    heartbeats = relationship("UserHeartbeat", back_populates="user", cascade="all, delete-orphan")
    live_locations = relationship("LiveLocation", back_populates="user", cascade="all, delete-orphan")
    segment_pnrs = relationship("SegmentPNR", back_populates="user", cascade="all, delete-orphan")

class UserSession(UserBase):
    __tablename__ = "user_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    device_info = Column(JSON, nullable=True) # E.g. {"os": "iOS", "browser": "Safari"}
    login_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    refresh_token_hash = Column(String(255), nullable=True) # For refresh token rotation
    
    user = relationship("User", back_populates="sessions")

class PersistentChatMessage(UserBase):
    __tablename__ = "persistent_chat_messages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    session_id = Column(String(100), index=True)
    role = Column(String(20)) # 'user' or 'assistant'
    content = Column(Text)
    actions = Column(JSON, nullable=True) # Store as JSON list
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="chat_history")

class AIIntentLog(UserBase):
    __tablename__ = "ai_intent_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    query = Column(Text, nullable=False)
    matched_intent = Column(String(100), nullable=False)
    confidence = Column(Float, default=0.0)
    intent_latency_ms = Column(Integer, default=0)
    llm_latency_ms = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="ai_intents")

class Profile(UserBase):
    __tablename__ = "profiles"
    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    
    # Medical & Safety (Task 16)
    blood_group = Column(String(5), nullable=True)
    medical_conditions = Column(Text, nullable=True)
    is_high_risk_passenger = Column(Boolean, default=False)
    karma_score = Column(Integer, default=100) # Task 32
    help_count = Column(Integer, default=0) # Task 32
    is_volunteer = Column(Boolean, default=False) # Task 39
    expertise = Column(String(50), nullable=True) # Task 39

    ai_memory = Column(JSON, default={}, nullable=False)

    user = relationship("User", back_populates="profile")

class LiveLocation(UserBase):
    __tablename__ = "live_locations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="live_locations")

class Booking(UserBase):
    __tablename__ = "bookings"
    __table_args__ = (
        Index('idx_booking_user_date', 'user_id', 'travel_date'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_number: Mapped[Optional[str]] = mapped_column(String(10), unique=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    travel_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    booking_status: Mapped[str] = mapped_column(String(50), default="pending", index=True) # Confirmed, Waitlist, etc.
    status = synonym("booking_status")
    payment_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    escrow_status: Mapped[EscrowStatus] = mapped_column(SQLEnum(EscrowStatus), default=EscrowStatus.CREATED)
    escrow_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # Pipeline sub-status message

    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    upi_tx_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    upi_utr_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True) # [45.7]
    utr_number: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True, index=True)
    merchant_vpa: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # The rotated VPA used for this booking
    
    # Task 24: Support for multiple transactions (Split/Partial payments)
    transaction_history = Column(JSON, default=[], nullable=True) 
    
    # Task 38: Tatkal & Priority
    is_tatkal = Column(Boolean, default=False)
    priority = Column(Integer, default=10) # 0 = Highest, 10 = Normal
    
    # NEW: Compliant Service Logic
    service_type: Mapped[str] = mapped_column(String(20), default="UNLOCK") # UNLOCK, AGENT_BOOKING
    is_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    
    train_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    berth_preference = Column(String(20), nullable=True)
    
    # [Task 45.1] Identity Link
    fingerprint_id = Column(String(36), ForeignKey("identity_fingerprints.id"), nullable=True)
    
    booking_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    route_id = Column(String(36), nullable=True)
    trip_id = Column(Integer, nullable=True)
    ticket_pdf_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True) # Task 26
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    passenger_details = relationship("PassengerDetails", back_populates="booking")

class BookingIdempotency(UserBase):
    """
    [REQ-005] Prevents duplicate booking charges by tracking idempotency keys.
    Stores the idempotency_key, booking_id, request_hash, created_at, and expires_at.
    """
    __tablename__ = "booking_idempotency"
    idempotency_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash of the request
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    booking = relationship("Booking")

    __table_args__ = (
        Index('ix_booking_idempotency_idempotency_key', 'idempotency_key', unique=True),
    )

class DailyReconciliation(UserBase):
    __tablename__ = "daily_reconciliations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recon_date = Column(Date, unique=True, nullable=False, index=True)
    total_revenue = Column(Float, default=0.0)
    total_agent_commissions = Column(Float, default=0.0)
    variance_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BookingMonitor(UserBase):
    """
    Task 15: Database model for booking monitoring and alerting state.
    """
    __tablename__ = "booking_monitors"
    booking_id: Mapped[str] = mapped_column(String(36), primary_key=True) # References Booking.id
    id: Mapped[str] = synonym("booking_id")
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    pnr_number: Mapped[Optional[str]] = mapped_column(String(10), index=True, nullable=True)
    train_number: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    travel_date: Mapped[Optional[date]] = mapped_column(Date, index=True, nullable=True)
    
    # Last known status snapshots for change detection
    last_known_live_status: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_known_pnr_status: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_known_fare_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Monitoring controls
    is_monitoring_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    alert_preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, default={}) 
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def validate_escrow_transition(self, new_status: EscrowStatus) -> bool:
        allowed = {
            EscrowStatus.CREATED: [EscrowStatus.UTR_SUBMITTED, EscrowStatus.FAILED],
            EscrowStatus.UTR_SUBMITTED: [EscrowStatus.VERIFIED, EscrowStatus.FAILED],
            EscrowStatus.VERIFIED: [EscrowStatus.BOOKING_INITIATED, EscrowStatus.FAILED, EscrowStatus.COMPLETED],
            EscrowStatus.BOOKING_INITIATED: [EscrowStatus.COMPLETED, EscrowStatus.FAILED, EscrowStatus.VERIFIED],
            EscrowStatus.COMPLETED: [],
            EscrowStatus.FAILED: [EscrowStatus.REFUNDED, EscrowStatus.UTR_SUBMITTED],
            EscrowStatus.REFUNDED: [],
        }
        return new_status in allowed.get(self.escrow_status, [])

    def update_escrow_status(self, db: Session, new_status: EscrowStatus, message: Optional[str] = None, performed_by: str = "SYSTEM", reason: Optional[str] = None):
        if not self.validate_escrow_transition(new_status):
            logger.warning(f"Illegal state transition attempted: {self.escrow_status} -> {new_status} for Booking {self.booking_id}")
            raise ValueError(f"Transition from {self.escrow_status} to {new_status} is not allowed.")

        old_status_val = self.escrow_status.value if hasattr(self.escrow_status, 'value') else str(self.escrow_status)
        new_status_val = new_status.value if hasattr(new_status, 'value') else str(new_status)

        self.escrow_status = new_status
        if message:
            self.escrow_message = message
        
        audit = AuditLog(
            entity_type="Booking",
            entity_id=self.booking_id,
            action="ESCROW_TRANSITION",
            old_value=old_status_val,
            new_value=new_status_val,
            performed_by=performed_by,
            reason=reason or message or ""
        )
        db.add(audit)
        logger.info(f"Booking {self.booking_id} transition: {old_status_val} -> {new_status_val}")

class PassengerDetails(UserBase):
    __tablename__ = "passenger_details"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    phone_number = Column(String(20), nullable=True) # Updated to match schema
    email = Column(String(100), nullable=True)
    document_type = Column(String(20), nullable=True)
    document_number = Column(String(50), nullable=True)
    concession_type = Column(String(50), nullable=True)
    concession_discount = Column(Float, default=0.0)
    meal_preference = Column(String(50), nullable=True)
    berth_preference = Column(String(20), nullable=True)
    booking = relationship("Booking", back_populates="passenger_details")

class BookingRequest(UserBase, TimestampMixin, AuditMixin):
    __tablename__ = "booking_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    source_station: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_station: Mapped[str] = mapped_column(String(20), nullable=False)
    journey_date: Mapped[date] = mapped_column(Date, nullable=False)
    train_number: Mapped[str] = mapped_column(String(20), nullable=False)
    train_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    class_type: Mapped[str] = mapped_column(String(10), nullable=False, default="AC_THREE_TIER")
    quota: Mapped[str] = mapped_column(String(10), nullable=False, default="GENERAL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_VERIFIED")
    payment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("payments.id"), nullable=True)
    route_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    verification_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    passengers = relationship("BookingRequestPassenger", back_populates="booking_request", cascade="all, delete-orphan")
    queue_entry = relationship("BookingQueue", back_populates="booking_request", uselist=False)

class BookingRequestPassenger(UserBase, TimestampMixin, AuditMixin):
    __tablename__ = "booking_request_passengers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_request_id: Mapped[str] = mapped_column(String(36), ForeignKey("booking_requests.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    berth_preference: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    id_proof_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    id_proof_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    booking_request = relationship("BookingRequest", back_populates="passengers")

class BookingQueue(UserBase, TimestampMixin, AuditMixin):
    __tablename__ = "booking_queue"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_request_id: Mapped[str] = mapped_column(String(36), ForeignKey("booking_requests.id"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="WAITING")
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    executed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    execution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    booking_request = relationship("BookingRequest", back_populates="queue_entry")

class SeatInventory(UserBase):
    """
    [Core Inventory] High-performance seat inventory tracking.
    Task 20: Optimized state for search and booking.
    """
    __tablename__ = "seat_inventory"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    train_number = Column(String(20), index=True)
    from_station_code = Column(String(10), index=True)
    to_station_code = Column(String(10), index=True)
    journey_date = Column(Date, index=True)
    class_type = Column(String(10), index=True)
    quota = Column(String(10), index=True)
    total_seats = Column(Integer, default=0)
    available_seats: Mapped[int] = mapped_column(Integer, default=0)
    status_text = Column(String(100)) # e.g. "AVAILABLE 20", "WL 5"
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_by_booking_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    travel_date = synonym("journey_date")

SeatAvailability = SeatInventory # Alias for backward compatibility

class CancelledTrain(TransitBase):
    """
    [Task 122.9] Tracks train cancellations for specific dates.
    Used by Orchestrator to filter results before hydration.
    """
    __tablename__ = "cancelled_trains"
    train_no = Column(String(20), primary_key=True)
    travel_date = Column(Date, primary_key=True)
    reason = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint('train_no', 'travel_date', name='uix_cancelled_train_date'),
    )

class TrainMaster(TransitBase):
    """[Core] Master list of trains."""
    __tablename__ = "trains_master"
    train_number = Column(String(20), primary_key=True)
    train_name = Column(String(255))
    source = Column(String(20))
    destination = Column(String(20))
    days_of_run = Column(JSON)
    train_type = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow)

class Trip(TransitBase):
    """[GTFS] Represents a specific trip instance."""
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    trip_id = Column(String(50), unique=True, index=True)
    train_number: Mapped[Optional[str]] = mapped_column("train_no", String(20), index=True)
    train_no = synonym("train_number")
    route_id = Column(String(50), index=True)
    service_id = Column(String(50), index=True)
    direction_id = Column(Integer, default=0)
    route_type = Column(Integer, nullable=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

class Segment(TransitBase):
    """[GTFS] A segment of a trip between two stops."""
    __tablename__ = "segments"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    to_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    departure_time = Column(Time)
    arrival_time = Column(Time)
    distance_km = Column(Float)
    stop_sequence = Column(Integer)

class StopTime(TransitBase):
    """[GTFS] Arrival/Departure times for a trip at a stop."""
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    arrival_time = Column(Text) # Stored as TEXT in SQLite
    departure_time = Column(Text)
    stop_sequence = Column(Integer)
    pickup_type = Column(Integer, default=0, nullable=True)
    drop_off_type = Column(Integer, default=0, nullable=True)
    platform_code = Column(String(20), nullable=True)
    arrival_timestamp = Column(Integer, nullable=True)
    departure_timestamp = Column(Integer, nullable=True)

class TrainAvailabilityCache(UserBase):
    __tablename__ = "train_availability_cache"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    train_number = Column(String(20), index=True)
    from_station_code = Column(String(10), index=True)
    to_station_code = Column(String(10), index=True)
    journey_date = Column(Date, index=True)
    class_type = Column(String(10), index=True)
    quota = Column(String(10), index=True)
    status_text = Column(String(100)) # e.g. "AVAILABLE-0120"
    seats_available = Column(Integer, default=0)
    fare = Column(Float, default=0.0)
    ticket_fare = Column(Float, default=0.0)
    catering_charge = Column(Float, default=0.0)
    alt_cnf_seat = Column(Boolean, default=False)
    alt_seat_status = Column(String(100), nullable=True)
    alt_seat_fare = Column(Float, nullable=True)
    raw_payload = Column(Text, nullable=True)
    last_updated_at = Column(DateTime, default=datetime.utcnow)


class QuotaInventory(UserBase):
    __tablename__ = "quota_inventory"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_id = Column(String(36), ForeignKey("seat_inventory.id"))
    quota_type: Mapped[QuotaType] = mapped_column(SQLEnum(QuotaType), index=True)
    allocated_seats = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
    max_allocation = Column(Integer, default=0)

class WaitlistQueue(UserBase):
    __tablename__ = "waitlist_queue"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_id = Column(String(36), ForeignKey("seat_inventory.id"))
    user_id = Column(String(36), ForeignKey("users.id"))
    waitlist_position = Column(Integer)
    passengers_json = Column(JSON)
    preferences_json = Column(JSON, nullable=True)
    status: Mapped[BookingStatus] = mapped_column(SQLEnum(BookingStatus), default=BookingStatus.WAITLIST)
    created_at = Column(DateTime, default=datetime.utcnow)
    promoted_at = Column(DateTime, nullable=True)

class Coach(UserBase):
    __tablename__ = "coaches"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    coach_number = Column(String(10))
    class_type = Column(String(50))
    total_seats = Column(Integer, default=0)

class Seat(UserBase):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"))
    seat_number = Column(String(10))
    is_available = Column(Boolean, default=True)

class Fare(UserBase):
    __tablename__ = "fares"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("segments.id"), nullable=True)
    trip_id: Mapped[int] = mapped_column(Integer, ForeignKey("trips.id"))
    class_type: Mapped[str] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Float)

class TrainLiveUpdate(UserBase):
    __tablename__ = "train_live_updates"
    id = Column(Integer, primary_key=True)
    train_number = Column(String(50), index=True)
    station_code = Column(String(100))
    station_name = Column(String(255))
    sequence = Column(Integer)
    distance_km = Column(Float)
    scheduled_arrival = Column(DateTime)
    scheduled_departure = Column(DateTime)
    actual_arrival = Column(DateTime)
    actual_departure = Column(DateTime)
    delay_minutes = Column(Integer, default=0)
    platform = Column(String(20))
    halt_minutes = Column(Integer)
    status = Column(String(100))
    is_current_station = Column(Boolean, default=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(100))

class RealtimeData(Base):
    __tablename__ = "realtime_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, index=True)
    entity_id = Column(String, index=True)
    data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String, default='new')

class TrainState(Base):
    __tablename__ = "train_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, unique=True, index=True)
    train_number = Column(String, index=True)
    current_delay_minutes = Column(Integer, default=0)
    status = Column(String)
    platform_number = Column(String, nullable=True)
    current_station_code = Column(String, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_update_source = Column(String, nullable=True)

class Disruption(Base):
    __tablename__ = "disruptions"
    id = Column(String(36), primary_key=True)
    route_id = Column(String(36), nullable=False, index=True)
    disruption_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    disruption_date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=True, index=True)
    severity = Column(String(50), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

class TrainRunningStatusCache(TransitBase):
    """
    [Gap 10] Caches NTES scraped running status for fast access.
    Multi-layer caching: Redis (3 min) -> Postgres (History).
    """
    __tablename__ = "train_running_status_cache"
    id = Column(Integer, primary_key=True)
    train_number = Column(String(20), index=True)
    journey_date = Column(Date, index=True)
    current_station = Column(String(255))
    delay_minutes = Column(Integer, default=0)
    running_status_text = Column(String(500))
    data_payload = Column(JSON) # Stores full station list snapshot
    last_updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('train_number', 'journey_date', name='uix_train_date'),
    )

class TrainStation(UserBase):
    __tablename__ = "train_stations"
    id = Column(Integer, primary_key=True)
    train_number = Column(String(20), index=True)
    stop_id = Column(String(50), index=True)
    arrival_time = Column(String(20))
    departure_time = Column(String(20))
    stop_sequence = Column(Integer)

class Transfer(UserBase):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    to_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    transfer_type = Column(Integer, default=0)
    min_transfer_time = Column(Integer, nullable=True)

class StationHealthIndex(UserBase):
    __tablename__ = "station_health_index"
    id = Column(Integer, primary_key=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), unique=True, nullable=True)
    station_code = Column(String(20), index=True, nullable=True)
    infrastructure_score = Column(Float, default=0.0)
    safety_score = Column(Float, default=0.0)
    cleanliness_score = Column(Float, default=0.0)
    last_audited = Column(DateTime, default=datetime.utcnow)

# --- GAP FIX MODELS ---

class APIBudget(UserBase):
    """
    Task 13: Observability System - Cost Management.
    Tracks budget limits and current spending for paid APIs (e.g., RapidAPI).
    """
    __tablename__ = "api_budgets"
    id = Column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50), unique=True, index=True) # e.g. 'RapidAPI'
    monthly_limit: Mapped[float] = mapped_column(Float, default=100.0) # $ USD
    current_spend: Mapped[float] = mapped_column(Float, default=0.0)
    last_reset_at = Column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cost_per_request = Column(Float, default=0.01) # Default avg cost per success
    
    # Alert thresholds
    warning_threshold_percent = Column(Float, default=80.0) # Alert dev at 80%
    critical_threshold_percent = Column(Float, default=95.0) # Cut off at 95%
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MetroStationGroup(TransitBase):
    """[Gap 1] Database-driven metropolitan station groups."""
    __tablename__ = "metro_station_groups"
    id = Column(Integer, primary_key=True)
    group_name = Column(String(100), index=True) # e.g., 'DELHI'
    station_code = Column(String(20), index=True) # e.g., 'NDLS'
    is_primary = Column(Boolean, default=False)

class StationClusterMapping(TransitBase):
    """[Gap 19] GTFS-level clusters (e.g., same physical station, multiple codes)."""
    __tablename__ = "station_cluster_mapping"
    cluster_id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"), primary_key=True)

class StationTypeConfig(TransitBase):
    """[Gap 2] Standardized transfer penalties by station size."""
    __tablename__ = "station_type_configs"
    station_size = Column(String(50), primary_key=True) # e.g., 'major_hub'
    transfer_penalty_minutes = Column(Integer, nullable=False)
    description = Column(String(255))

class StationTransitIndexBin(TransitBase):
    """[Gap 5] Binary transit index with versioning."""
    __tablename__ = "station_transit_index_bin"
    station_code = Column(String(20), primary_key=True)
    transit_blob = Column(LargeBinary, nullable=False)
    version = Column(Integer, default=3) # V3 or V4
    last_updated = Column(DateTime, default=datetime.utcnow)

class TimeIndexKey(TransitBase):
    """Maps bitmap ids to entity types and ids."""
    __tablename__ = "time_index_keys"
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    
class Stop(TransitBase):
    """
    GTFS Stops.
    Task 1: Core graph node.
    """
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True)
    stop_id = Column(String(50), index=True)
    code = Column(String(20), index=True)
    name = Column(String(255))
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    is_major_junction = Column(Boolean, default=False)
    hub_type = Column(String(50), nullable=True)
    zone = Column(String(10), nullable=True)
    connectivity_score = Column(Float, default=0.0)
    
    def __repr__(self):
        return f"<Stop(name='{self.name}', code='{self.code}')>"

class Calendar(TransitBase):
    """GTFS Service Calendar."""
    __tablename__ = "calendar"
    service_id = Column(String(100), primary_key=True)
    monday = Column(Integer)
    tuesday = Column(Integer)
    wednesday = Column(Integer)
    thursday = Column(Integer)
    friday = Column(Integer)
    saturday = Column(Integer)
    sunday = Column(Integer)
    start_date = Column(String(10)) # YYYYMMDD
    end_date = Column(String(10))

class CalendarDate(TransitBase):
    """GTFS Service Calendar Exceptions."""
    __tablename__ = "calendar_dates"
    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), ForeignKey("calendar.service_id"), index=True)
    date = Column(String(10), index=True) # YYYYMMDD
    exception_type = Column(Integer) # 1 = add, 2 = remove

class StationDeparture(TransitBase):
    """Indexed departure records precomputed from stop times."""
    __tablename__ = "station_departures_indexed"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trip_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    departure_time: Mapped[time] = mapped_column(Time, nullable=False, index=True)
    arrival_time_at_next: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    next_station_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    operating_days: Mapped[str] = mapped_column(String(7), nullable=False, default="1111111")
    train_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    distance_to_next: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

class StationDepartureBucket(TransitBase):
    """Minute bucket bitmap for station departures."""
    __tablename__ = "station_departures"
    id = Column(String(36), primary_key=True)
    station_id = Column(String(36), nullable=False, index=True)
    bucket_start_minute = Column(Integer, nullable=False)
    bitmap = Column(LargeBinary, nullable=False)
    trips_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class StopDepartureBucket(TransitBase):
    """Minute bucket bitmap for GTFS stop departures."""
    __tablename__ = "stop_departures"
    id = Column(String(36), primary_key=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    bucket_start_minute = Column(Integer, nullable=False)
    bitmap = Column(LargeBinary, nullable=False)
    trips_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class StationRealtimeHeartbeat(TransitBase):
    """
    [Point 36 & 38] Proactive Data Freshness Store.
    Stores pre-fetched delays, cancellations, and status for major stations.
    """
    __tablename__ = "station_realtime_heartbeats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    status_summary: Mapped[str] = mapped_column(String(255)) # e.g. "8 trains delayed, 2 cancelled"
    trains_json: Mapped[List[Any]] = mapped_column(JSON) # Detailed pulse of all trains at this station
    sync_latency_ms: Mapped[int] = mapped_column(Integer)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_updated_unix: Mapped[int] = mapped_column(BigInteger, index=True) # [P7] For sub-ms lookups
    station_mode: Mapped[str] = mapped_column(String(20), default="RAIL") # [P11] RAIL, METRO, BUS, TAXI_HUB
    connectivity_score: Mapped[float] = mapped_column(Float, default=1.0) # [P11] Inter-modal efficiency rank
    
    # [Task 41.B] Social Empowerment & Ground Support
    guardian_score: Mapped[float] = mapped_column(Float, default=0.0) # 0.0 to 1.0 based on safety/support presence
    active_agents_count: Mapped[int] = mapped_column(Integer, default=0) # Number of ground agents available
    
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    sync_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # [P7] Integrity comparison

    __table_args__ = (
        Index("idx_station_heartbeat_lookup", "station_code", "expires_at"),
    )

class SOSEvent(UserBase):
    __tablename__ = "sos_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    priority = Column(String(20), default="high")
    category = Column(String(50), nullable=True)
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # [Production Hardening] Contact Details (for guest or overrides)
    name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    
    # Real-time Location Snapshot (Last known summary)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalation_level = Column(Integer, default=1)
    
    # Store complex JSON fields
    call_logs = Column(JSON, default=[])
    chat_history = Column(JSON, default=[])
    structured_info = Column(JSON, default={})
    active_participants = Column(JSON, default=[])
    trip_data = Column(JSON, nullable=True) # PNR, train number, etc.

    telemetry = relationship("SOSTelemetry", back_populates="event", cascade="all, delete-orphan")
    user = relationship("User", backref="sos_events")

    __table_args__ = (
        Index("idx_sos_active_lookup", "user_id", "status"),
        Index("idx_sos_phone_lookup", "phone"),
    )

class SOSTelemetry(UserBase):
    __tablename__ = "sos_telemetry"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("sos_events.id"), index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    battery_level = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    event = relationship("SOSEvent", back_populates="telemetry")

class EmergencyContact(UserBase):
    __tablename__ = "emergency_contacts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    relation = Column(String(50), nullable=True) # e.g. Parent, Spouse
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="emergency_contacts")

class UserHeartbeat(UserBase):
    """
    [Point 20] Proactive Safety Tracking.
    Tracks a passenger during high-risk transfers.
    """
    __tablename__ = "user_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    journey_id = Column(String(100), index=True)
    pnr = Column(String(10), nullable=True)
    
    # Checkpoint Logic
    current_segment_index: Mapped[int] = mapped_column(Integer, default=0)
    last_station_code: Mapped[str] = mapped_column(String(10))
    next_check_in_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    
    status: Mapped[str] = mapped_column(String(20), default="ON_TRACK") # ON_TRACK, MISSED_CHECKIN, SOS_TRIGGERED
    
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="heartbeats")

class SearchOutcome(UserBase):
    __tablename__ = "search_outcomes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    search_id: Mapped[str] = mapped_column(String(36), index=True) # Correlates to RouteSearchLog
    journey_id: Mapped[str] = mapped_column(String(100), index=True)
    
    # Prediction Snapshots
    predicted_value_score: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_confirm_chance: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # Actual Outcomes
    is_clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)
    final_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # e.g. CNF, WL_CANCELLED
    
    # Safety Truth
    had_sos_event: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_delay_mins: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Feedback for ML
    discrepancy_score: Mapped[float] = mapped_column(Float, default=0.0) # (Actual - Predicted)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SegmentPNR(UserBase):
    __tablename__ = "segment_pnrs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    journey_id: Mapped[str] = mapped_column(String(36), index=True)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    train_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pnr: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="segment_pnrs")

class Payment(UserBase):
    """Payment transaction details."""
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), index=True)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razorpay_signature: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    route_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("precalculated_routes.id"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    merchant_vpa: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    refund_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    refund_status: Mapped[str] = mapped_column(String(50), default="NOT_APPLICABLE")
    refund_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", backref="payments")
    user = relationship("User", backref="payments", foreign_keys=[user_id])
    route = relationship("PrecalculatedRoute", foreign_keys=[route_id])
    unlocked_route = relationship("UnlockedRoute", back_populates="payment")

class PaymentTransaction(UserBase):
    """
    [REQ-011] Payment Reconciliation
    Stores all payment transactions for reconciliation purposes.
    Tracks payment_id, booking_id, amount, method, status, provider_reference, and utr_number.
    """
    __tablename__ = "payment_transactions"
    
    payment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # UPI, CARD, NET_BANKING, etc.
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")  # pending, success, failed, refunded
    provider_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Payment provider's transaction ID
    utr_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # UPI Transaction Reference Number
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", backref="payment_transactions")

    __table_args__ = (
        Index('ix_payment_transactions_payment_id', 'payment_id'),
        Index('ix_payment_transactions_booking_id', 'booking_id'),
        Index('ix_payment_transactions_utr_number', 'utr_number'),
        Index('ix_payment_transactions_status', 'status'),
        Index('ix_payment_transactions_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<PaymentTransaction(payment_id='{self.payment_id}', amount={self.amount}, method='{self.method}', status='{self.status}')>"

class Wallet(UserBase):
    """
    [P18] Unified Wallet Engine.
    Stores agent commissions and user credits (Karma).
    """
    __tablename__ = "wallets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    pending_commission: Mapped[float] = mapped_column(Float, default=0.0)
    total_earned: Mapped[float] = mapped_column(Float, default=0.0)
    last_payout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref=backref("wallet", uselist=False))

# AgentWallet is an alias of Wallet for services that distinguish agent-specific wallets.
AgentWallet = Wallet

class CreditTransaction(UserBase):
    """[Task 42.A / P18] Unified Credit and Karma Audit Trail."""
    __tablename__ = "credit_transactions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    wallet_id = Column(String(36), ForeignKey("wallets.id"), nullable=True)
    amount = Column(Float, nullable=False) # Supports both Integer credits and Float currency
    transaction_type = Column(String(50)) # PURCHASE, CONSUMPTION, BONUS, REFUND, AGENT_COMMISSION
    balance_before = Column(Float, nullable=True)
    balance_after = Column(Float, nullable=True)
    reason = Column(String(255), nullable=True)
    reference_entity_id = Column(String(100), nullable=True) # Booking ID, Payment ID, or Outcome ID
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    wallet = relationship("Wallet", backref="transactions")

# ==============================================================================
# SATHI MODELS (Women/Family Safety System)
# ==============================================================================

# Import Sathi models
from .sathi_models import (
    Sathi,
    SathiAssignment,
    SathiRating,
    FamilyGroup,
    JourneyPlan,
    SathiVerificationStatus,
    SathiCertificationLevel,
    SathiSpecialization,
)

class FinancialLedger(UserBase):
    """[Task 1.2] High-Integrity Financial Ledger with lifecycle support."""
    __tablename__ = "financial_ledger"
    id = Column(Integer, primary_key=True)
    transaction_uuid = Column(String(36), default=lambda: str(uuid.uuid4()), index=True)
    debit_account = Column(String(50), nullable=False)
    credit_account = Column(String(50), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False)
    metadata_json = Column(JSON, default={})
    previous_row_hash = Column(String(64), nullable=True)
    cumulative_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class UnlockedRoute(UserBase):
    """[Task 41] Records routes unlocked by users."""
    __tablename__ = "unlocked_routes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    route_id: Mapped[str] = mapped_column(String(100), index=True)
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("payments.id"), nullable=True, index=True)
    cached_route_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="unlocked_routes")
    payment = relationship("Payment", back_populates="unlocked_route")

class PaymentSession(UserBase):
    """[Task 41.4] Tracks payment sessions for unlocks/bookings."""
    __tablename__ = "payment_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    route_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    session_code: Mapped[str] = mapped_column(String(50), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING") # PENDING, SUCCESS, FAILED
    verification_details: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# Placeholder models for missing User relationships
class Review(UserBase):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    booking_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="reviews")

class RLFeedbackLog(UserBase):
    __tablename__ = "rl_feedback_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    rating = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")

class CommissionTracking(UserBase):
    __tablename__ = "commission_tracking"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    payout_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="commission_tracks")

class WebhookEvent(UserBase):
    """Tracks webhook events to avoid duplicate processing."""
    __tablename__ = "webhook_events"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Refund(UserBase):
    """Records refund events from payment providers."""
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("payments.id"), nullable=True, index=True)
    razorpay_refund_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IdentityFingerprint(UserBase):
    __tablename__ = "identity_fingerprints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128), index=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

class FraudAlert(UserBase):
    __tablename__ = "fraud_alerts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    alert_type = Column(String(50))
    severity = Column(String(20))
    status = Column(String(20), default="PENDING")
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class BookingFraudCheck(UserBase):
    """
    [REQ-008] Stores fraud detection results for each booking.
    Tracks check_type, risk_score, flags, and decision for audit and analysis.
    """
    __tablename__ = "booking_fraud_checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[str] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # ALLOWED, BLOCKED, REVIEW
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", foreign_keys=[booking_id])
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index('ix_booking_fraud_checks_booking_id', 'booking_id'),
        Index('ix_booking_fraud_checks_user_id', 'user_id'),
        Index('ix_booking_fraud_checks_check_type', 'check_type'),
    )

class Subscription(UserBase):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    plan_tier: Mapped[str] = mapped_column(String(20), default="FREE")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user = relationship("User", back_populates="subscription")

class PlatformConfig(UserBase):
    __tablename__ = "platform_config"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RouteSearchLog(UserBase):
    __tablename__ = "route_search_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    user = relationship("User", back_populates="route_search_logs")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    src: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dst: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Synonyms for backward compatibility
    timestamp = synonym("created_at")
    origin_city = synonym("src")
    destination_city = synonym("dst")

class UserAIPreference(UserBase):
    __tablename__ = "user_ai_preferences"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    user = relationship("User", back_populates="ai_preferences")

class SearchAccuracyMetric(UserBase):
    __tablename__ = "search_accuracy_metrics"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    search_id = Column(String(36), index=True) # Correlates to RouteSearchLog
    journey_id = Column(String(100), index=True)
    
    # Prediction Snapshots
    predicted_value_score = Column(Float)
    predicted_confirm_chance = Column(Float)
    metadata_snapshot = Column(JSON)
    
    # Actual Outcomes
    is_clicked = Column(Boolean, default=False)
    is_booked = Column(Boolean, default=False)
    final_status = Column(String(20), nullable=True) # e.g. CNF, WL_CANCELLED
    
    # Safety Truth
    had_sos_event = Column(Boolean, default=False)
    actual_delay_mins = Column(Integer, nullable=True)
    
    # Feedback for ML
    discrepancy_score = Column(Float, default=0.0) # (Actual - Predicted)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelDriftEvent(UserBase):
    __tablename__ = "model_drift_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_name = Column(String(100))
    metric_type = Column(String(50))
    baseline_value = Column(Float)
    current_value = Column(Float)
    deviation = Column(Float)
    severity = Column(String(20))
    status = Column(String(20), default="DETECTED")
    detected_at = Column(DateTime, default=datetime.utcnow)

# --- BOOKING AUDIT LOG MODEL ---
class AuditLog(Base):
    """Generic Audit Log for all entities."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), index=True)
    entity_id = Column(String(100), index=True)
    action = Column(String(100))
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, nullable=True)

class BookingAuditLog(Base): # Inherits from Base directly
    """
    Immutable audit log for booking operations.
    Task: Booking compliance audit trail.
    """
    __tablename__ = 'booking_audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_id = Column(String(36), unique=True, nullable=False, index=True)
    booking_id = Column(String(50), nullable=True, index=True)
    pnr_number = Column(String(20), nullable=True, index=True)
    action = Column(String(50), nullable=False)  # CREATE, CONFIRM, CANCEL, PAY, REFUND
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    actor_type = Column(String(20), nullable=False)  # SYSTEM, USER, ADMIN, API
    actor_id = Column(String(100), nullable=True)
    amount = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    extra_data = Column('metadata', JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def compute_checksum(data: Dict) -> str:
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
# ==============================================================================
# SYNC SERVICE MODELS
# ==============================================================================

class SearchEvent(UserBase):
    """
    Tracks user search events for analytics and hot zone detection.
    """
    __tablename__ = "search_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # Search parameters
    src = Column(String(20), nullable=False, index=True)
    dest = Column(String(20), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    # Search context
    device_type = Column(String(50), nullable=True)
    platform = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Results
    routes_found = Column(Integer, default=0)
    filters_applied = Column(JSON, nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)


class RecommendationEvent(UserBase):
    """
    Tracks recommendation events and user responses.
    """
    __tablename__ = "recommendation_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    
    # Recommendation context
    recommendation_type = Column(String(50), nullable=False)
    source_route = Column(String(20), nullable=True)
    destination_route = Column(String(20), nullable=True)
    
    # Recommendation details
    recommended_item = Column(JSON, nullable=True)
    confidence_score = Column(Float, default=0.0)
    reasoning = Column(Text, nullable=True)
    
    # User response
    was_clicked = Column(Boolean, default=False, index=True)
    was_booked = Column(Boolean, default=False, index=True)
    was_dismissed = Column(Boolean, default=False)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    clicked_at = Column(DateTime, nullable=True)
    booked_at = Column(DateTime, nullable=True)


class PrecalculatedRoute(UserBase):
    """
    Stores precalculated routes for fast retrieval.
    """
    __tablename__ = "precalculated_routes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    src = Column(String(20), nullable=False, index=True)
    dest = Column(String(20), nullable=False, index=True)
    travel_date = Column(Date, nullable=False, index=True)
    
    route_data = Column(JSON, nullable=False)
    total_duration_minutes = Column(Integer, nullable=True)
    total_distance_km = Column(Float, nullable=True)
    number_of_transfers = Column(Integer, default=0)
    
    reliability_score = Column(Float, default=0.9)
    popularity_score = Column(Float, default=0.5)
    
    calculated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('ix_precalc_route_lookup', 'src', 'dest', 'travel_date'),
    )


# ==============================================================================
# KNOWLEDGE GRAPH MODELS
# ==============================================================================

class UserPreferenceModel(UserBase):
    """
    Stores learned user preferences for the knowledge graph.
    """
    __tablename__ = "knowledge_user_preferences"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), unique=True, nullable=False, index=True)
    
    preferred_class = Column(String(10), default="SL")
    preferred_time_morning = Column(Integer, default=0)
    class_flexibility = Column(Float, default=0.5)
    price_sensitivity = Column(Float, default=0.5)
    
    preferred_stations = Column(Text, default="")
    preferred_routes = Column(Text, default="")
    preferred_times = Column(Text, default="")
    preferred_days = Column(Text, default="")
    
    avg_booking_advance_days = Column(Integer, default=7)
    cancellation_rate = Column(Float, default=0.1)
    avg_trip_duration_hours = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    interaction_count = Column(Integer, default=0)


class RoutePatternModel(UserBase):
    """
    Stores learned route patterns and statistics.
    """
    __tablename__ = "knowledge_route_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    searches = Column(Integer, default=0)
    bookings = Column(Integer, default=0)
    cancellations = Column(Integer, default=0)
    
    success_rate = Column(Float, default=0.85)
    avg_booking_value = Column(Float, default=0.0)
    avg_booking_advance_days = Column(Float, default=0.0)
    
    peak_hours = Column(Text, default="")
    peak_days = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SeasonalPatternModel(UserBase):
    """
    Stores seasonal demand patterns for routes.
    """
    __tablename__ = "knowledge_seasonal_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    month = Column(Integer, nullable=False)
    
    demand_score = Column(Float, default=0.5)
    avg_price = Column(Float, default=0.0)
    availability_rate = Column(Float, default=1.0)
    
    demand_level = Column(String(20), default="medium")
    trend = Column(String(20), default="stable")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompetitorPriceModel(UserBase):
    """
    Stores competitor pricing information.
    """
    __tablename__ = "knowledge_competitor_prices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(20), nullable=False, index=True)
    destination = Column(String(20), nullable=False, index=True)
    
    provider_name = Column(String(100), nullable=False)
    provider_type = Column(String(50), default="aggregator")
    
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    
    service_class = Column(String(10), nullable=True)
    departure_time = Column(String(10), nullable=True)
    journey_duration_minutes = Column(Integer, nullable=True)
    
    collected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    url = Column(String(1024), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserBehaviorModel(UserBase):
    """
    Stores user behavior data for collaborative filtering.
    """
    __tablename__ = "knowledge_user_behaviors"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    
    interaction_type = Column(String(50), nullable=False)
    
    source = Column(String(20), nullable=False)
    destination = Column(String(20), nullable=False)
    
    score = Column(Float, default=1.0)
    
    device_type = Column(String(50), nullable=True)
    platform = Column(String(50), nullable=True)
    
    interaction_timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class StationPatternModel(UserBase):
    """
    Stores learned station patterns and characteristics.
    """
    __tablename__ = "knowledge_station_patterns"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_code = Column(String(20), unique=True, nullable=False, index=True)
    station_name = Column(String(255), nullable=True)
    
    region = Column(String(100), nullable=True)
    zone = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    
    connectivity_score = Column(Float, default=0.5)
    route_count = Column(Integer, default=0)
    hub_score = Column(Float, default=0.0)
    
    avg_delay_minutes = Column(Float, default=0.0)
    cancellation_rate = Column(Float, default=0.0)
    on_time_rate = Column(Float, default=0.9)
    
    peak_hours = Column(Text, default="")
    busy_days = Column(Text, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeGraphSnapshot(UserBase):
    """
    Stores knowledge graph snapshots for backup and versioning.
    """
    __tablename__ = "knowledge_graph_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    snapshot_name = Column(String(100), nullable=False)
    version = Column(String(20), default="1.0.0")
    
    total_stations = Column(Integer, default=0)
    total_routes = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    total_interactions = Column(Integer, default=0)
    
    graph_data = Column(JSON, nullable=True)
    preferences_data = Column(JSON, nullable=True)
    patterns_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(36), nullable=True)
    description = Column(Text, nullable=True)

# =========================================================================
# INTELLIGENCE & TELEMETRY MODELS (Task INT-5)
# =========================================================================

class IntelligenceSearchEvent(UserBase):
    """Captures raw search intent."""
    __tablename__ = "intelligence_search_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    src: Mapped[str] = mapped_column(String(20), nullable=False)
    dst: Mapped[str] = mapped_column(String(20), nullable=False)
    persona: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class IntelligenceRecommendationEvent(UserBase):
    """Captures system recommendations."""
    __tablename__ = "intelligence_recommendation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("intelligence_search_events.id"), index=True)
    route_id: Mapped[str] = mapped_column(String(100), index=True)
    engine: Mapped[str] = mapped_column(String(50))
    rank: Mapped[Optional[int]] = mapped_column(Integer)
    value_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=1.0)
    availability_prob: Mapped[float] = mapped_column(Float, default=0.5)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ConversionEvent(UserBase):
    """Captures user conversions (Unlock, Book)."""
    __tablename__ = "intelligence_conversion_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("intelligence_recommendation_events.id"), index=True)
    user_action: Mapped[str] = mapped_column(String(50)) # CLICK, UNLOCK, BOOK
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SafetyEvent(UserBase):
    """Validates risk predictions vs reality."""
    __tablename__ = "intelligence_safety_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String(100), index=True)
    predicted_risk = Column(Float)
    actual_outcome = Column(String(50)) # SUCCESS, DELAY, SOS
    delay_minutes = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

class IntelligenceMetric(UserBase):
    """Stores granular intelligence metrics."""
    __tablename__ = "intelligence_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_key: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class GlobalIntelligenceState(UserBase):
    """Stores auto-tuned global scoring weights."""
    __tablename__ = "intelligence_global_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    w_availability: Mapped[float] = mapped_column(Float, default=0.4)
    w_speed: Mapped[float] = mapped_column(Float, default=0.3)
    w_comfort: Mapped[float] = mapped_column(Float, default=0.2)
    w_safety: Mapped[float] = mapped_column(Float, default=0.1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_tuned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IntelligenceRouteSearchLog(UserBase):
    """Lightweight log for search volume analysis."""
    __tablename__ = "intelligence_route_search_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    src = Column(String(20), nullable=False, index=True)
    dst = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")

# ==============================================================================
# BACKWARD COMPATIBILITY ALIASES (for test imports)
# ==============================================================================

# Aliases for common imports that tests expect
Station = TrainStation
Route = Route  # Route is a dataclass in core.data_structures
Stop = Stop
StopTime = StopTime
Segment = Segment
TimeDependentGraph = None  # Import from core.route_engine.graph
StaticGraphSnapshot = None  # Import from core.route_engine.graph
RouteEngine = None  # Use RailwayRouteEngine from core.route_engine
OptimizedRAPTOR = None  # Import from core.route_engine.raptor

class MerchantVPA(Base):
    __tablename__ = "merchant_vpas"
    id = Column(Integer, primary_key=True, index=True)
    vpa = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    daily_limit = Column(Float, default=100000.0)
    current_daily_volume = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    last_reset_at = Column(DateTime, default=datetime.utcnow)

    # PATENT-LEVEL: Health Intelligence
    health_score = Column(Float, default=1.0) # 0.0 to 1.0
    failure_count = Column(Integer, default=0)
    last_failure_at = Column(DateTime, nullable=True)


class MerchantVPAVolumeSnapshot(Base):
    __tablename__ = "merchant_vpa_volume_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    vpa = Column(String, index=True)
    volume = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ETLMetadata(Base):
    __tablename__ = "etl_metadata"
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String)
    last_sync_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    record_count = Column(Integer, default=0)

class AdminDashboardSession(Base):
    __tablename__ = "admin_dashboard_sessions"
    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    expires_at = Column(DateTime)
    login_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)

AdminSession = AdminDashboardSession

class RefundQueue(Base):
    __tablename__ = "refund_queue"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(String)
    amount = Column(Float)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

class DemandTrainingData(Base):
    __tablename__ = "ml_demand_training_data"
    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String(50), index=True)
    destination = Column(String(50), index=True)
    hour = Column(Integer)
    day_of_week = Column(Integer) # 0-6
    demand_score = Column(Float) # The 'ground truth' observed demand
    conversion_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, index=True)
    intent = Column(String)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class NotificationToken(Base):
    __tablename__ = "notification_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    channel = Column(String)
    token = Column(String)
    is_active = Column(Boolean, default=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    channel = Column(String)

class GroupTrip(Base):
    __tablename__ = "user_trips"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(String(50), unique=True, index=True, nullable=False)
    group_id = Column(String(100), index=True, nullable=True) # Telegram Group ID
    origin = Column(String(50), nullable=False)
    destination = Column(String(50), nullable=False)
    travel_date = Column(DateTime, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class TripParticipant(Base):
    __tablename__ = "trip_participants"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(String(36), ForeignKey("user_trips.id"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Store individual context
    telegram_id = Column(String(100), index=True)
    is_enabled = Column(Boolean, default=True)

class UnclaimedFund(Base):
    __tablename__ = "unclaimed_funds"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    utr_number = Column(String, unique=True, index=True)
    amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class StationRank(Base):
    __tablename__ = "station_rank"
    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stops.id"), index=True)
    hub_type = Column(String)  # major_hub, junction, terminal, etc.
    rank_score = Column(Float, default=0.0)
    daily_footfall = Column(Integer, default=0)
    zone = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)

class TelegramSession(UserBase):
    """
    Manages conversational state for Telegram users.
    Supports multi-step flows like search -> select -> book.
    """
    __tablename__ = "telegram_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    current_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # e.g. 'search', 'booking'
    current_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # e.g. 'awaiting_route', 'awaiting_selection'
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default={}, nullable=False) # Stores search params, selected train, etc.
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class TelegramAccount(UserBase):
    """
    Maps Telegram users to RouteMaster users.
    Supports multiple Telegram accounts per user.
    """
    __tablename__ = "telegram_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    telegram_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", backref="telegram_accounts")

# ==============================================================================
# NOTIFICATION LOG MODEL (Task 1.1.5)
# ==============================================================================

class NotificationLog(UserBase):
    """
    [REQ-015] Tracks notification delivery for retry logic.
    Stores notification_id, booking_id, channel (SMS/email/push), status, retry_count, and error_message.
    Indexes on booking_id and status for efficient querying and retry processing.
    """
    __tablename__ = "notification_logs"
    
    notification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bookings.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # SMS, EMAIL, PUSH
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)  # pending, sent, delivered, failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    booking = relationship("Booking", foreign_keys=[booking_id])
    
    __table_args__ = (
        Index('ix_notification_logs_booking_id', 'booking_id'),
        Index('ix_notification_logs_status', 'status'),
        Index('ix_notification_logs_channel', 'channel'),
        Index('ix_notification_logs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<NotificationLog(notification_id='{self.notification_id}', channel='{self.channel}', status='{self.status}')>"
