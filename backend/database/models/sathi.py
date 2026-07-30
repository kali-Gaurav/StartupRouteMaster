"""
Sathi (Guide/Companion) Database Models
Core to the women/family safety vision
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text, Enum, LargeBinary, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column, backref
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from enum import Enum as PyEnum
from database.infrastructure.base import UserBase, TransitBase, Base

class SathiVerificationStatus(PyEnum):
    """Sathi verification lifecycle"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    KYC_COMPLETE = "kyc_complete"
    POLICE_VERIFIED = "police_verified"
    TRAINING_COMPLETE = "training_complete"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"

class SathiCertificationLevel(PyEnum):
    """Sathi certification levels"""
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"
    EXPERT = "expert"

class SathiSpecialization(PyEnum):
    """Sathi specializations"""
    WOMEN_SAFETY = "women_safety"
    FAMILY_TRAVEL = "family_travel"
    ELDERLY_CARE = "elderly_care"
    CHILD_CARE = "child_care"
    MEDICAL_FIRST_AID = "medical_first_aid"
    LUGGAGE_ASSISTANCE = "luggage_assistance"
    LANGUAGE_TRANSLATION = "language_translation"
    DISABILITY_ASSISTANCE = "disability_assistance"

class Sathi(UserBase):
    """
    Sathi (Guide/Companion) model
    Represents verified human guides ensuring passenger safety
    """
    __tablename__ = "sathis"
    __table_args__ = (
        Index('idx_sathis_service_stations', 'service_stations', postgresql_using='gin'),
        Index('idx_sathis_service_routes', 'service_routes', postgresql_using='gin'),
        {"extend_existing": True}
    )

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Personal Information
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Verification & Status
    verification_status: Mapped[str] = mapped_column(
        String(20), 
        default=SathiVerificationStatus.PENDING.value
    )
    background_check_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    police_verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    training_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    activation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Skills & Capabilities
    certification_level: Mapped[str] = mapped_column(
        String(20), 
        default=SathiCertificationLevel.BASIC.value
    )
    specializations: Mapped[List[str]] = mapped_column(JSON, default=[])
    languages_spoken: Mapped[List[str]] = mapped_column(JSON, default=[])
    
    # Service Areas
    service_stations: Mapped[List[str]] = mapped_column(JSONB, default=[])
    service_routes: Mapped[List[str]] = mapped_column(JSONB, default=[])
    max_distance_km: Mapped[float] = mapped_column(Float, default=50.0)
    
    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    availability_schedule: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})
    next_available_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_available_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Performance Metrics
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    total_assignments: Mapped[int] = mapped_column(Integer, default=0)
    successful_assignments: Mapped[int] = mapped_column(Integer, default=0)
    karma_score: Mapped[float] = mapped_column(Float, default=100.0)
    response_time_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Location
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_location_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    home_station_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Financial
    hourly_rate: Mapped[float] = mapped_column(Float, default=100.0)
    commission_rate: Mapped[float] = mapped_column(Float, default=15.0)
    
    # Safety & Compliance
    has_first_aid_certification: Mapped[bool] = mapped_column(Boolean, default=False)
    has_safety_training: Mapped[bool] = mapped_column(Boolean, default=False)
    criminal_record_clear: Mapped[bool] = mapped_column(Boolean, default=False)
    last_safety_refresh: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="sathi_profile")
    assignments = relationship("SathiAssignment", back_populates="sathi")
    ratings = relationship("SathiRating", back_populates="sathi")
    
    def __repr__(self):
        return f"<Sathi {self.full_name} ({self.verification_status})>"

    def can_transition_to(self, next_status: SathiVerificationStatus) -> bool:
        """Task 1.2: Strict State Machine for Verification"""
        transitions = {
            SathiVerificationStatus.PENDING: [SathiVerificationStatus.SUBMITTED, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.SUBMITTED: [SathiVerificationStatus.KYC_COMPLETE, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.KYC_COMPLETE: [SathiVerificationStatus.POLICE_VERIFIED, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.POLICE_VERIFIED: [SathiVerificationStatus.TRAINING_COMPLETE, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.TRAINING_COMPLETE: [SathiVerificationStatus.ACTIVE, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.ACTIVE: [SathiVerificationStatus.SUSPENDED, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.SUSPENDED: [SathiVerificationStatus.ACTIVE, SathiVerificationStatus.REJECTED],
            SathiVerificationStatus.REJECTED: [SathiVerificationStatus.SUBMITTED] # Allow re-submission
        }
        return next_status in transitions.get(SathiVerificationStatus(self.verification_status), [])

class SathiAssignment(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Assignment of Sathi to passenger journey
    """
    __tablename__ = "sathi_assignments"
    __table_args__ = {"extend_existing": True}

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sathi_id = Column(String(36), ForeignKey("sathis.id"), nullable=False, index=True)
    passenger_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    journey_id = Column(String(100), nullable=False, index=True)  # Could be PNR or journey UUID
    
    # Assignment Details
    assignment_type = Column(String(20), default="scheduled")  # scheduled, on_demand, emergency
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, accepted, active, completed, cancelled
    
    # Timing
    requested_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expected_duration_minutes = Column(Integer, nullable=True)
    
    # Location Details
    start_station_code = Column(String(10), nullable=False)
    end_station_code = Column(String(10), nullable=False)
    meeting_point = Column(String(255), nullable=True)  # Specific meeting location
    
    # Safety Context
    safety_context = Column(JSON, default={})  # Women safety, family travel, etc.
    emergency_contacts_notified = Column(Boolean, default=False)
    family_group_id = Column(String(36), nullable=True)  # If part of family group
    
    # Communication
    chat_channel_id = Column(String(100), nullable=True)  # WebSocket/Telegram channel
    voice_call_id = Column(String(100), nullable=True)  # Voice call session ID
    
    # Payment
    payment_status = Column(String(20), default="pending")
    amount_charged = Column(Float, nullable=True)
    commission_earned = Column(Float, nullable=True)
    
    # Feedback
    passenger_rating = Column(Float, nullable=True)
    passenger_feedback = Column(Text, nullable=True)
    sathi_rating = Column(Float, nullable=True)
    sathi_feedback = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sathi = relationship("Sathi", back_populates="assignments")
    passenger = relationship("User", foreign_keys=[passenger_id])
    
    def __repr__(self):
        return f"<SathiAssignment {self.sathi_id} -> {self.passenger_id} ({self.status})>"

class SathiRating(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Detailed rating for Sathi performance
    """
    __tablename__ = "sathi_ratings"
    __table_args__ = {"extend_existing": True}

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sathi_id = Column(String(36), ForeignKey("sathis.id"), nullable=False, index=True)
    assignment_id = Column(String(36), ForeignKey("sathi_assignments.id"), nullable=True)
    passenger_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Rating Categories (1-5)
    safety_score = Column(Float, nullable=False)
    professionalism_score = Column(Float, nullable=False)
    communication_score = Column(Float, nullable=False)
    punctuality_score = Column(Float, nullable=False)
    knowledge_score = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)
    
    # Feedback
    positive_feedback = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    would_recommend = Column(Boolean, nullable=True)
    
    # Context
    journey_context = Column(JSON, nullable=True)  # Journey details
    safety_incidents = Column(Integer, default=0)  # Number of safety incidents handled
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sathi = relationship("Sathi", back_populates="ratings")
    
    def __repr__(self):
        return f"<SathiRating {self.sathi_id}: {self.overall_score}>"

class FamilyGroup(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Family group for tracking multiple travelers
    """
    __tablename__ = "family_groups"
    __table_args__ = {"extend_existing": True}

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    group_name = Column(String(255), nullable=False)
    
    # Members
    members = Column(JSON, default=[])  # List of user IDs
    member_roles = Column(JSON, default={})  # {user_id: role}
    
    # Settings
    notification_preferences = Column(JSON, default={
        "sos_alerts": True,
        "journey_updates": True,
        "checkpoint_alerts": True,
        "delay_alerts": True,
        "sathi_assignment": True
    })
    
    # Safety Settings
    auto_share_location = Column(Boolean, default=True)
    require_check_ins = Column(Boolean, default=True)
    check_in_interval_minutes = Column(Integer, default=30)
    
    # Emergency Contacts
    emergency_contacts = Column(JSON, default=[])
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    
    def __repr__(self):
        return f"<FamilyGroup {self.group_name}>"

class JourneyPlan(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    Planned journey with safety checkpoints
    """
    __tablename__ = "journey_plans"
    __table_args__ = {"extend_existing": True}

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    passenger_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    family_group_id = Column(String(36), ForeignKey("family_groups.id"), nullable=True, index=True)
    
    # Journey Details
    journey_type = Column(String(20), default="train")  # train, bus, flight, multi_modal
    start_station_code = Column(String(10), nullable=False)
    end_station_code = Column(String(10), nullable=False)
    planned_departure = Column(DateTime, nullable=False)
    planned_arrival = Column(DateTime, nullable=False)
    
    # Route Details
    route_details = Column(JSON, nullable=False)  # Full route with segments
    pnr_numbers = Column(JSON, default=[])  # List of PNRs if booked
    train_numbers = Column(JSON, default=[])  # List of train numbers
    
    # Safety Configuration
    safety_level = Column(String(20), default="standard")  # standard, enhanced, maximum
    requires_sathi = Column(Boolean, default=False)
    sathi_preferences = Column(JSON, default={})  # Gender, languages, certifications
    
    # Checkpoints
    checkpoints = Column(JSON, default=[])  # List of {station_code, expected_time, check_in_required}
    next_checkpoint_index = Column(Integer, default=0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned, active, completed, cancelled
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Notifications
    family_notified_at = Column(DateTime, nullable=True)
    sathi_assigned_at = Column(DateTime, nullable=True)
    
    # Safety Incidents
    safety_incidents = Column(Integer, default=0)
    last_incident_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    passenger = relationship("User", foreign_keys=[passenger_id])
    family_group = relationship("FamilyGroup", foreign_keys=[family_group_id])
    
    def __repr__(self):
        return f"<JourneyPlan {self.start_station_code} -> {self.end_station_code} ({self.status})>"

class SathiIdentity(UserBase):
    __table_args__ = {"extend_existing": True}
    """
    [Task 1.1] Aadhar & UIDAI Secure Schema
    Stores PII in a highly protected manner.
    """
    __tablename__ = "sathi_identities"
    __table_args__ = {"extend_existing": True}

    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sathi_id: Mapped[str] = mapped_column(String(36), ForeignKey("sathis.id"), unique=True, index=True)
    
    # Encrypted PII
    aadhar_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    encrypted_aadhar_number: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Metadata
    uidai_reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verification_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    sathi = relationship("Sathi", backref=backref("identity_secure", uselist=False))
