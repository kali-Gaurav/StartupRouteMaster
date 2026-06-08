"""
Safety Schemas - Pydantic models for safety and SOS features.
"""

from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel, Field


class SafetyLevel(str, Enum):
    """Safety level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SOSRequest(BaseModel):
    """SOS trigger request."""
    booking_id: str
    location: Optional[Dict[str, float]] = Field(None, description="GPS coordinates {lat, lng}")
    description: Optional[str] = Field(None, max_length=500)
    emergency_type: Optional[str] = Field("general", description="Type of emergency")


class SOSResponse(BaseModel):
    """SOS response."""
    sos_id: str
    status: str
    emergency_contacts_notified: int
    safety_score: int
    recommendations: List[str]


class SafetyAlertRequest(BaseModel):
    """Safety alert request."""
    station_code: Optional[str] = None
    route_from: Optional[str] = None
    route_to: Optional[str] = None
    alert_type: str
    severity: SafetyLevel
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)
    recommendations: Optional[List[str]] = None
    expires_at: datetime


class SafetyAlertResponse(BaseModel):
    """Safety alert response."""
    alert_id: str
    type: str
    severity: str
    message: str
    station_code: Optional[str] = None
    expires_at: datetime


class EmergencyContact(BaseModel):
    """Emergency contact."""
    id: str
    name: str
    phone: str
    relationship: str
    priority: int = 1


class EmergencyContactCreate(BaseModel):
    """Create emergency contact request."""
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern="^[0-9]{10,15}$")
    email: Optional[str] = None
    relationship: str = Field(..., max_length=50)
    priority: int = Field(1, ge=1, le=10)


class SafetyScore(BaseModel):
    """Safety score response."""
    overall: int
    station: int
    coach: int
    route: int
    time: int
    level: SafetyLevel
    factors: List[str]
    recommendations: List[str]


class SafetyIncidentReport(BaseModel):
    """Report safety incident."""
    booking_id: str
    incident_type: str = Field(..., description="harassment, theft, medical, other")
    description: str = Field(..., min_length=10, max_length=2000)
    location: Optional[Dict[str, float]] = None
    evidence: Optional[List[str]] = Field(None, description="URLs to evidence")


class SafetyIncidentResponse(BaseModel):
    """Safety incident response."""
    incident_id: str
    status: str
    message: str