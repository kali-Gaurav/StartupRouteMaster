from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, DateTime, Boolean, ForeignKey, JSON, Text, 
    LargeBinary, CheckConstraint, UniqueConstraint, Date, Index, Time, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, declarative_base, backref, Session
from datetime import datetime
import uuid
import enum
import logging

from database.session import UserBase, TransitBase

logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================

from core.data_structures import QuotaType, BookingStatus, EscrowStatus, Persona, AllocationStatus

class CoachClass(enum.Enum):
    SL = "sl"
    AC3 = "ac3"
    AC2 = "ac2"
    AC1 = "ac1"
    CC = "cc"
    EC = "ec"

# ==============================================================================
# USER STORE MODELS (user_store.db)
# ==============================================================================

class User(UserBase):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=True, index=True)
    supabase_id = Column(String(255), unique=True, nullable=True, index=True)
    phone_number = Column(String(20), nullable=True)
    role = Column(String(50), default="user")
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, nullable=True)
    
    # Task 3.1: Telegram Integration
    telegram_id = Column(String(100), unique=True, nullable=True, index=True)
    telegram_link_token = Column(String(100), unique=True, nullable=True, index=True)
    telegram_link_expiry = Column(DateTime, nullable=True)
    
    # Task 35: Credential Vault
    encrypted_irctc_creds = Column(LargeBinary, nullable=True)
    creds_iv = Column(LargeBinary, nullable=True)
    opt_in_persistent_creds = Column(Boolean, default=False)
    
    # [Task 42.A] Token Economy
    credit_balance = Column(Integer, default=0)
    bonus_credit_balance = Column(Integer, default=0)
    total_lifetime_credits = Column(Integer, default=0)
    
    # [Task 43.A] Referral & Karma Engine
    referral_code = Column(String(12), unique=True, index=True)
    referred_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    karma_score = Column(Integer, default=0)
    referral_status = Column(String(20), default="INITIATED") # INITIATED, CONVERTED
    last_fingerprint = Column(String(64), nullable=True) # [45.1]

    bookings = relationship("Booking", back_populates="user", foreign_keys="[Booking.user_id]")
    profile = relationship("Profile", back_populates="user", uselist=False)
    reviews = relationship("Review", back_populates="user")
    commission_tracks = relationship("CommissionTracking", back_populates="user")
    unlocked_routes = relationship("UnlockedRoute", back_populates="user")
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    route_search_logs = relationship("RouteSearchLog", back_populates="user")
    ai_preferences = relationship("UserAIPreference", back_populates="user", uselist=False)
    chat_history = relationship("PersistentChatMessage", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")

class UserSession(UserBase):
    __tablename__ = "user_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    device_info = Column(JSON, nullable=True) # E.g., {"os": "iOS", "browser": "Safari"}
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

class Booking(UserBase):
    __tablename__ = "bookings"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pnr_number = Column(String(10), unique=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    travel_date = Column(Date, index=True)
    booking_status = Column(String(50), default="pending") # Confirmed, Waitlist, etc.
    escrow_status = Column(SQLEnum(EscrowStatus), default=EscrowStatus.CREATED)
    escrow_message = Column(String(255), nullable=True) # Pipeline sub-status message
    
    amount_paid = Column(Float, default=0.0)
    upi_tx_id = Column(String(100), unique=True, index=True)
    upi_utr_hash = Column(String(64), unique=True, nullable=True, index=True) # [45.7]
    utr_number = Column(String(12), unique=True, nullable=True, index=True)
    merchant_vpa = Column(String(100), nullable=True) # The rotated VPA used for this booking
    
    # Task 24: Support for multiple transactions (Split/Partial payments)
    transaction_history = Column(JSON, default=[], nullable=True) 
    
    # Task 38: Tatkal & Priority
    is_tatkal = Column(Boolean, default=False)
    priority = Column(Integer, default=10) # 0 = Highest, 10 = Normal
    
    # NEW: Compliant Service Logic
    service_type = Column(String(20), default="UNLOCK") # UNLOCK, AGENT_BOOKING
    is_unlocked = Column(Boolean, default=False)
    agent_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    train_number = Column(String(20), nullable=True)
    berth_preference = Column(String(20), nullable=True)
    
    booking_details = Column(JSON, nullable=True)
    
    route_id = Column(String(36), nullable=True)
    trip_id = Column(Integer, nullable=True)
    ticket_pdf_url = Column(String(1024), nullable=True) # Task 26
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    passenger_details = relationship("PassengerDetails", back_populates="booking")

class BookingMonitor(UserBase):
    """
    Task 15: Database model for booking monitoring and alerting state.
    """
    __tablename__ = "booking_monitors"
    booking_id = Column(String(36), primary_key=True) # References Booking.id
    user_id = Column(String(36), ForeignKey("users.id"))
    pnr_number = Column(String(10), index=True, nullable=True)
    train_number = Column(String(20), index=True, nullable=True)
    travel_date = Column(Date, index=True, nullable=True)
    
    # Last known status snapshots for change detection
    last_known_live_status = Column(JSON, nullable=True)
    last_known_pnr_status = Column(JSON, nullable=True)
    last_known_fare_details = Column(JSON, nullable=True)
    
    # Monitoring controls
    is_monitoring_active = Column(Boolean, default=True)
    last_check_timestamp = Column(DateTime, nullable=True)
    alert_preferences = Column(JSON, default={}) 
    
    created_at = Column(DateTime, default=datetime.utcnow)

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

    def update_escrow_status(self, db: Session, new_status: EscrowStatus, message: str = None, performed_by: str = "SYSTEM", reason: str = None):
        if not self.validate_escrow_transition(new_status):
            logger.warning(f"Illegal state transition attempted: {self.escrow_status} -> {new_status} for Booking {self.id}")
            raise ValueError(f"Transition from {self.escrow_status} to {new_status} is not allowed.")

        old_status_val = self.escrow_status.value if hasattr(self.escrow_status, 'value') else str(self.escrow_status)
        new_status_val = new_status.value if hasattr(new_status, 'value') else str(new_status)

        self.escrow_status = new_status
        if message:
            self.escrow_message = message
        
        audit = AuditLog(
            entity_type="Booking",
            entity_id=self.id,
            action="ESCROW_TRANSITION",
            old_value=old_status_val,
            new_value=new_status_val,
            performed_by=performed_by,
            reason=reason or message
        )
        db.add(audit)
        logger.info(f"Booking {self.id} transition: {old_status_val} -> {new_status_val}")

class PassengerDetails(UserBase):
    __tablename__ = "passenger_details"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    booking = relationship("Booking", back_populates="passenger_details")

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

class RefundQueue(UserBase):
    __tablename__ = "refund_queue"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    vpa = Column(String(100), nullable=False)
    status = Column(String(20), default="PENDING")
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

class BankTransaction(UserBase):
    __tablename__ = "bank_transactions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    utr_number = Column(String(50), unique=True, index=True)
    event_id = Column(String(100), unique=True, index=True, nullable=True) # [21.1]
    amount = Column(Float, nullable=False)
    bank_name = Column(String(50))
    raw_sms = Column(Text)
    sender_vpa = Column(String(100), nullable=True)
    sender_phone = Column(String(20))
    received_at = Column(DateTime, default=datetime.utcnow)
    is_reconciled = Column(Boolean, default=False)
    status = Column(String(50), default="PENDING")

class MerchantVPA(UserBase):
    __tablename__ = "merchant_vpas"
    vpa = Column(String(100), primary_key=True)
    name = Column(String(100), default="RouteMaster")
    daily_limit = Column(Float, default=100000.0)
    current_daily_volume = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    last_reset_at = Column(DateTime, default=datetime.utcnow) # Added
    last_volume_update = Column(DateTime, default=datetime.utcnow)

class MerchantVPAVolumeSnapshot(UserBase):
    __tablename__ = "merchant_vpa_volume_snapshots"
    id = Column(Integer, primary_key=True)
    vpa = Column(String(100), index=True)
    volume = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AuditLog(UserBase):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False) # 'Booking', 'System', 'Admin'
    entity_id = Column(String(36), nullable=False, index=True)
    action = Column(String(50), nullable=False) # 'STATUS_TRANSITION', 'SENSITIVE_VIEW', etc.
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    performed_by = Column(String(50), default="SYSTEM")
    reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class CreditTransaction(UserBase):
    """
    [Task 42.A] Tracks all credit consumption and top-ups.
    """
    __tablename__ = "credit_transactions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    amount = Column(Integer, nullable=False) # Positive for top-up, negative for consumption
    transaction_type = Column(String(20)) # PURCHASE, CONSUMPTION, BONUS, REFUND, MOMENTUM_BONUS
    balance_before = Column(Integer)
    balance_after = Column(Integer)
    reference_entity_id = Column(String(36), nullable=True) # Booking ID or Payment ID
    timestamp = Column(DateTime, default=datetime.utcnow)

class PlatformConfig(UserBase):
    """
    Subtask 25.1: Dynamic Platform Configuration.
    Stores real-time settings for fees, maintenance, and system thresholds.
    """
    __tablename__ = "platform_configs"
    key = Column(String(50), primary_key=True) # 'MAINTENANCE_MODE', 'UNLOCK_FEE', etc.
    value = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VPABlacklist(UserBase):
    """
    Subtask 28.1: UPI Fraud Prevention.
    Stores blacklisted sender VPAs to prevent malicious payment attempts.
    """
    __tablename__ = "vpa_blacklist"
    vpa = Column(String(100), primary_key=True)
    reason = Column(String(255), nullable=True)
    blacklisted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class AdminSession(UserBase):
    __tablename__ = "admin_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = Column(String(50), index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    geo_state = Column(String(50), nullable=True)
    login_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)
    session_token = Column(String(255), unique=True)

class AdminDashboardSession(UserBase):
    __tablename__ = "admin_dashboard_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_username = Column(String(50), index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

class AIIntentLog(UserBase):
    __tablename__ = "ai_intent_logs"
    id = Column(Integer, primary_key=True)
    query = Column(Text)
    matched_intent = Column(String(100), nullable=True)
    confidence = Column(Float)
    llm_latency_ms = Column(Integer)
    intent_latency_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

class RouteSearchLog(UserBase):
    __tablename__ = "route_search_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    src = Column(String(255), nullable=False)
    dst = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    latency_ms = Column(Float, nullable=True)
    ip_address = Column(String(50), nullable=True)
    geo_state = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="route_search_logs")

class UserAIPreference(UserBase):
    __tablename__ = "user_ai_preferences"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True)
    preferred_language = Column(String(20), default="en")
    persona_bias = Column(Float, default=0.5)
    user = relationship("User", back_populates="ai_preferences")

class RLFeedbackLog(UserBase):
    __tablename__ = "rl_feedback_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    prompt = Column(Text)
    response = Column(Text)
    rating = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Payment(UserBase):
    __tablename__ = "payments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True)
    status = Column(String(50), default="CREATED")
    amount = Column(Float, nullable=False)

class Subscription(UserBase):
    __tablename__ = "subscriptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    is_pro = Column(Boolean, default=False)
    
    # [Task 41.1] Multi-Tier Multi-Quota
    plan_tier = Column(String(20), default="FREE") # FREE, PRO, ELITE
    features = Column(JSON, default={}) # {"max_unlocks": 100, "priority_agent": true}
    
    expires_at = Column(DateTime, nullable=True) # [41.3] For subscription expiry
    
    user = relationship("User", back_populates="subscription")

class UnlockedRoute(UserBase):
    __tablename__ = "unlocked_routes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=True)
    user = relationship("User", back_populates="unlocked_routes")

class Review(UserBase):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    booking_id = Column(String(36), ForeignKey("bookings.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    user = relationship("User", back_populates="reviews")

class CommissionTracking(UserBase):
    __tablename__ = "commission_tracking"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id')) # The Agent
    booking_id = Column(String(36), ForeignKey('bookings.id'), unique=True)
    amount = Column(Float, default=10.0)
    commission_type = Column(String(50), default="FIXED_AGENT_FEE")
    status = Column(String(20), default="PENDING") # PENDING, SETTLED, DISPUTED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)
    disputed_at = Column(DateTime, nullable=True) # [44.6]
    payout_id = Column(String(100), nullable=True)
    
    user = relationship("User", back_populates="commission_tracks")
    booking = relationship("Booking")

class AgentWallet(UserBase):
    """
    [Task 44.3] Aggregated balance for agents.
    """
    __tablename__ = "agent_wallets"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, index=True)
    total_earned = Column(Float, default=0.0)
    pending_commission = Column(Float, default=0.0)
    last_payout_at = Column(DateTime, nullable=True)
    
    user = relationship("User", backref=backref("wallet", uselist=False))

class PaymentSession(UserBase):
    __tablename__ = "payment_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    route_id = Column(String(36), nullable=True)
    booking_id = Column(String(36), ForeignKey("bookings.id"), nullable=True) # [22.1]
    session_code = Column(String(20), unique=True, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(50), default="PENDING")
    payment_method = Column(String(50), nullable=True)
    verification_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class IdentityFingerprint(UserBase):
    """
    [Task 45.1] Device Fingerprinting for Fraud Prevention.
    Stores cryptographic hashes of browser/OS/IP combos.
    """
    __tablename__ = "identity_fingerprints"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    fingerprint_hash = Column(String(64), unique=True, index=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    is_trusted = Column(Boolean, default=True)
    risk_score = Column(Float, default=0.0) # 0.0 - 1.0
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref=backref("fingerprints", cascade="all, delete-orphan"))

class FraudAlert(UserBase):
    """
    [Task 45.10] Log of suspicious activities.
    """
    __tablename__ = "fraud_alerts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    alert_type = Column(String(50)) # IMPOSSIBLE_TRAVEL, SYBIL_ATTACK, REPEAT_UTR
    severity = Column(String(20)) # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(20), default="OPEN") # OPEN, UNDER_REVIEW, RESOLVED, BANNED
    metadata_json = Column(JSON, default={})
    timestamp = Column(DateTime, default=datetime.utcnow)

class WebhookEvent(UserBase):
    __tablename__ = "webhook_events"
    id = Column(String(100), primary_key=True)
    event_type = Column(String(50))
    payload = Column(JSON)
    processed_at = Column(DateTime, default=datetime.utcnow)

class DailyReconciliation(UserBase):
    """
    Task 49.1: Daily Financial Balance reporting.
    """
    __tablename__ = "daily_reconciliation"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recon_date = Column(Date, unique=True, index=True)
    total_revenue = Column(Float, default=0.0)
    total_agent_commissions = Column(Float, default=0.0)
    total_unlocked_fees = Column(Float, default=0.0)
    variance_amount = Column(Float, default=0.0)
    status = Column(String(20), default="MATCHED") # MATCHED, VARIANCE, PENDING
    report_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class NotificationToken(UserBase):
    """
    [Task 46.1] Multi-channel notification registry (FCM, Telegram, etc).
    """
    __tablename__ = "notification_tokens"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    channel = Column(String(20)) # WEB_PUSH, TELEGRAM, MOBILE_APP
    token = Column(Text, nullable=False) # FCM Token or Chat ID
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref=backref("notification_tokens", cascade="all, delete-orphan"))

class UserAlert(UserBase):
    """
    [Task 46.1] In-app notification center history.
    """
    __tablename__ = "user_alerts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    title = Column(String(100))
    body = Column(Text)
    alert_type = Column(String(20)) # BOOKING, PNR, SYSTEM, FRAUD, PROMOTION
    priority = Column(Integer, default=10) # 0 = CRITICAL (SOS), 10 = Normal
    is_read = Column(Boolean, default=False)
    payload = Column(JSON, default={})
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref=backref("alerts", cascade="all, delete-orphan"))

class NotificationPreference(UserBase):
    """
    [Task 46.1] Granular user DND/Opt-out controls.
    """
    __tablename__ = "notification_preferences"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True)
    enable_pnr_updates = Column(Boolean, default=True)
    enable_promotions = Column(Boolean, default=True)
    enable_security_alerts = Column(Boolean, default=True) # Usually forced true
    quiet_hours_start = Column(Time, nullable=True) # Suggestion 2
    quiet_hours_end = Column(Time, nullable=True)
    
    user = relationship("User", backref=backref("notification_prefs", uselist=False))

class FinancialLedger(UserBase):
    """
    [Task 49.1] Double-Entry Ledger with Cryptographic Hash Chain.
    This is the core for Project Sentinel S3 (Audit Log).
    """
    __tablename__ = "financial_ledger"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_uuid = Column(String(36), index=True, default=lambda: str(uuid.uuid4()))
    
    # Double-entry accounts
    debit_account = Column(String(50), index=True)  # e.g., 'CASH_ESCROW', 'USER_WALLET'
    credit_account = Column(String(50), index=True) # e.g., 'AGENT_BALANCE', 'PLATFORM_REVENUE'
    
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    
    transaction_type = Column(String(50)) # CREDIT_BUY, REFUND, COMMISSION_SETTLE
    metadata_json = Column(JSON, default={})
    
    # [Task 49.9] Cryptographic Tamper-Detection
    previous_row_hash = Column(String(64), nullable=True) # Hash of row ID-1
    cumulative_hash = Column(String(64), index=True)     # Hash(CurrentData + PreviousRowHash)
    
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="ledger_entries")

# ==============================================================================
# TRANSIT GRAPH MODELS (transit_graph.db)
# ==============================================================================

class Agency(TransitBase):
    __tablename__ = "agency"
    id = Column(Integer, primary_key=True)
    agency_id = Column(String(100), unique=True, index=True)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), default="Asia/Kolkata")

class Stop(TransitBase):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True)
    stop_id = Column(String(100), unique=True, index=True)
    code = Column(String(100), index=True)
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), index=True)
    state = Column(String(255))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    data_quality_score = Column(Integer, default=0)
    
    # [HUB EXPANSION]
    connectivity_score = Column(Float, default=0.0, index=True)
    hub_type = Column(String(50), default="regular")
    is_major_junction = Column(Boolean, default=False)
    
    stop_times = relationship("StopTime", back_populates="stop")
    facilities = relationship("StationFacilities", back_populates="stop", uselist=False)

class Route(TransitBase):
    __tablename__ = "gtfs_routes"
    id = Column(Integer, primary_key=True)
    route_id = Column(String(100), unique=True, nullable=False, index=True)
    short_name = Column(String(50))
    long_name = Column(String(255), nullable=False)
    route_type = Column(Integer, default=2)

class Calendar(TransitBase):
    __tablename__ = "calendar"
    service_id = Column(String(100), primary_key=True, index=True)
    monday = Column(Integer, default=1)
    tuesday = Column(Integer, default=1)
    wednesday = Column(Integer, default=1)
    thursday = Column(Integer, default=1)
    friday = Column(Integer, default=1)
    saturday = Column(Integer, default=1)
    sunday = Column(Integer, default=1)
    start_date = Column(String(20))
    end_date = Column(String(20))

class CalendarDate(TransitBase):
    __tablename__ = "calendar_dates"
    id = Column(Integer, primary_key=True)
    service_id = Column(String(100), ForeignKey("calendar.service_id"), index=True)
    date = Column(Date, nullable=False, index=True)
    exception_type = Column(Integer, default=1) # 1: added, 2: removed

class Trip(TransitBase):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    trip_id = Column(String(255), unique=True, index=True)
    route_id = Column(Integer, ForeignKey("gtfs_routes.id"))
    service_id = Column(String(100), ForeignKey("calendar.service_id"))
    stop_times = relationship("StopTime", back_populates="trip")

class Segment(TransitBase):
    __tablename__ = "segments"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True)
    source_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    destination_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    departure_time = Column(Time, nullable=False)
    arrival_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=True)
    fare = Column(Float, nullable=True)
    train_number = Column(String(50), index=True)
    train_name = Column(String(255))
    data_quality_score = Column(Integer, default=0)

class StopTime(TransitBase):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    stop_id = Column(Integer, ForeignKey("stops.id"))
    arrival_time = Column(Time, nullable=False)
    departure_time = Column(Time, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    shape_dist_traveled = Column(Float, nullable=True)
    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")

class StationFacilities(TransitBase):
    __tablename__ = "station_facilities"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stop_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    stop = relationship("Stop", back_populates="facilities")

class TrainMaster(TransitBase):
    __tablename__ = "trains_master"
    train_number = Column(String(50), primary_key=True)
    train_name = Column(String(255))

class TrainState(TransitBase):
    __tablename__ = "train_states"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, index=True)
    train_number = Column(String(50), index=True)
    status = Column(String(20), default="on_time")
    delay_minutes = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ETLMetadata(TransitBase):
    __tablename__ = "etl_metadata"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True)
    status = Column(String(20))
    trips_synced = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)
    source_version = Column(String(50), nullable=True)

class StationRank(TransitBase):
    __tablename__ = "station_rank"
    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, ForeignKey("stops.id"), unique=True)
    connectivity_score = Column(Float, default=0.0)
    hub_type = Column(String(50), default="regular")

class StationTransitIndex(TransitBase):
    __tablename__ = "station_transit_index"
    station_code = Column(String(20), primary_key=True)
    station_name = Column(String(255))
    trains_map = Column(Text)

class RealtimeData(TransitBase):
    __tablename__ = "realtime_data"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50))
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    data = Column(JSON)
    timestamp = Column(DateTime)
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Disruption(TransitBase):
    __tablename__ = "disruptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    disruption_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="active")
    created_by_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    gtfs_route_id = Column(Integer, ForeignKey("gtfs_routes.id"), nullable=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=True)

class SeatInventory(TransitBase):
    __tablename__ = "seat_inventory"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(Integer, ForeignKey("trips.id"), index=True)
    stop_time_id = Column(Integer, ForeignKey("stop_times.id"), nullable=True)
    travel_date = Column(Date, index=True)
    coach_type = Column(String(10), index=True)
    total_seats = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    locked_by_booking_id = Column(String(36), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Coach(TransitBase):
    __tablename__ = "coaches"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    coach_number = Column(String(10))
    class_type = Column(String(50))
    total_seats = Column(Integer, default=0)

class Seat(TransitBase):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"))
    seat_number = Column(String(10))
    is_available = Column(Boolean, default=True)

class Fare(TransitBase):
    __tablename__ = "fares"
    id = Column(Integer, primary_key=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    trip_id = Column(Integer, ForeignKey("trips.id"))
    class_type = Column(String(50))
    amount = Column(Float)

class TrainLiveUpdate(TransitBase):
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

class TrainStation(TransitBase):
    __tablename__ = "train_stations"
    id = Column(Integer, primary_key=True)
    train_number = Column(String(20), index=True)
    stop_id = Column(String(50), index=True)
    arrival_time = Column(String(20))
    departure_time = Column(String(20))
    stop_sequence = Column(Integer)

class Transfer(TransitBase):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    from_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    to_stop_id = Column(Integer, ForeignKey("stops.id"), index=True)
    transfer_type = Column(Integer, default=0)
    min_transfer_time = Column(Integer, nullable=True)

class StationHealthIndex(TransitBase):
    __tablename__ = "station_health_index"
    id = Column(Integer, primary_key=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), unique=True)
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
    provider_name = Column(String(50), unique=True, index=True) # e.g. 'RapidAPI'
    monthly_limit = Column(Float, default=100.0) # $ USD
    current_spend = Column(Float, default=0.0)
    last_reset_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
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
