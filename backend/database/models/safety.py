from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date, Time,
    Text, ForeignKey, Enum, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database.infrastructure.base import Base


class SafetyIncident(Base):
    """Safety incident tracking."""
    __tablename__ = "safety_incidents"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    
    # Incident details
    incident_type: Mapped[str] = mapped_column(String(50))  # sos_triggered, harassment, theft, etc.
    description: Mapped[Text] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="reported")  # reported, investigating, resolved
    
    # Location
    location: Mapped[Optional[Dict]] = mapped_column(JSON)
    station_code: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Evidence
    evidence: Mapped[Optional[List[str]]] = mapped_column(JSON)
    
    # Resolution
    resolution_notes: Mapped[Optional[Text]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_incidents_user", "user_id", "created_at"),
        Index("idx_incidents_status", "status", "created_at"),
        {"extend_existing": True}
    )


class UserEmergencyContact(Base):
    """User emergency contacts."""
    __tablename__ = "user_emergency_contacts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Contact info
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    relationship: Mapped[str] = mapped_column(String(50))
    
    # Priority (lower = higher priority)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("user_id", "phone", name="uq_user_phone"),
        {"extend_existing": True}
    )


class SafetyAlert(Base):
    """Safety alerts for stations/routes."""
    __tablename__ = "safety_alerts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(50))  # station_incident, route_issue, weather
    severity: Mapped[str] = mapped_column(String(20))  # low, medium, high, critical
    
    # Affected area
    station_code: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    affected_stations: Mapped[Optional[List[str]]] = mapped_column(JSON)
    route_from: Mapped[Optional[str]] = mapped_column(String(10))
    route_to: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Alert content
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[Text] = mapped_column(Text)
    recommendations: Mapped[Optional[List[str]]] = mapped_column(JSON)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_alerts_active", "is_active", "expires_at"),
        {"extend_existing": True}
    )
