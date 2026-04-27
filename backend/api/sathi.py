"""
Sathi (Guide/Companion) APIs
Core to women/family safety vision
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid

from database.session import get_db
from database.models import User, Sathi, SathiAssignment, FamilyGroup, JourneyPlan
from database.sathi_models import (
    SathiVerificationStatus, 
    SathiCertificationLevel,
    SathiSpecialization
)
from api.dependencies import get_current_user
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, cast
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sathi"])

# ==============================================================================
# PYDANTIC MODELS
# ==============================================================================

class SathiRegisterRequest(BaseModel):
    """Request to register as a Sathi"""
    full_name: str
    phone: str
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    languages_spoken: List[str] = Field(default=["en", "hi"])
    service_stations: List[str] = Field(default=[])
    specializations: List[str] = Field(default=[])
    has_first_aid_certification: bool = False
    has_safety_training: bool = False

class SathiProfileResponse(BaseModel):
    """Sathi profile response"""
    id: str
    full_name: str
    phone: str
    email: Optional[str]
    verification_status: str
    certification_level: str
    specializations: List[str]
    languages_spoken: List[str]
    rating: float
    total_assignments: int
    successful_assignments: int
    karma_score: float
    is_available: bool
    hourly_rate: float
    service_stations: List[str]
    has_first_aid_certification: bool
    has_safety_training: bool

class AvailableSathiRequest(BaseModel):
    """Request to find available Sathis"""
    station_code: str
    start_time: datetime
    end_time: datetime
    required_specializations: Optional[List[str]] = None
    required_languages: Optional[List[str]] = None
    gender_preference: Optional[str] = None
    max_distance_km: float = 50.0

class SathiAssignmentRequest(BaseModel):
    """Request to assign Sathi to journey"""
    sathi_id: str
    journey_id: str
    assignment_type: str = "scheduled"
    start_station_code: str
    end_station_code: str
    expected_duration_minutes: int
    safety_context: Dict[str, Any] = Field(default={})
    family_group_id: Optional[str] = None

class FamilyGroupCreateRequest(BaseModel):
    """Request to create family group"""
    group_name: str
    members: List[str]  # List of user IDs or emails
    notification_preferences: Optional[Dict[str, bool]] = None
    auto_share_location: bool = True
    require_check_ins: bool = True

class JourneyPlanRequest(BaseModel):
    """Request to create journey plan"""
    journey_type: str = "train"
    start_station_code: str
    end_station_code: str
    planned_departure: datetime
    planned_arrival: datetime
    route_details: Dict[str, Any]
    pnr_numbers: Optional[List[str]] = None
    train_numbers: Optional[List[str]] = None
    safety_level: str = "standard"
    requires_sathi: bool = False
    sathi_preferences: Optional[Dict[str, Any]] = None
    family_group_id: Optional[str] = None

# ==============================================================================
# SATHI REGISTRATION & PROFILE APIs
# ==============================================================================

@router.post("/register", response_model=SathiProfileResponse)
async def register_as_sathi(
    request: SathiRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register as a Sathi (Guide/Companion)
    """
    # Check if user is already registered as Sathi
    existing_sathi = db.query(Sathi).filter(Sathi.user_id == current_user.id).first()
    if existing_sathi:
        raise HTTPException(
            status_code=400,
            detail="User is already registered as a Sathi"
        )
    
    # Check if phone is already registered
    existing_phone = db.query(Sathi).filter(Sathi.phone == request.phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Phone number already registered"
        )
    
    # Create Sathi profile
    sathi = Sathi(
        user_id=current_user.id,
        full_name=request.full_name,
        phone=request.phone,
        email=request.email,
        age=request.age,
        gender=request.gender,
        languages_spoken=request.languages_spoken,
        service_stations=request.service_stations,
        specializations=request.specializations,
        has_first_aid_certification=request.has_first_aid_certification,
        has_safety_training=request.has_safety_training,
        verification_status=SathiVerificationStatus.SUBMITTED.value,
        certification_level=SathiCertificationLevel.BASIC.value,
        is_available=True
    )
    
    db.add(sathi)
    db.commit()
    db.refresh(sathi)
    
    logger.info(f"Sathi registered: {sathi.full_name} ({sathi.id})")
    
    return SathiProfileResponse(
        id=sathi.id,
        full_name=sathi.full_name,
        phone=sathi.phone,
        email=sathi.email,
        verification_status=sathi.verification_status,
        certification_level=sathi.certification_level,
        specializations=sathi.specializations,
        languages_spoken=sathi.languages_spoken,
        rating=sathi.rating,
        total_assignments=sathi.total_assignments,
        successful_assignments=sathi.successful_assignments,
        karma_score=sathi.karma_score,
        is_available=sathi.is_available,
        hourly_rate=sathi.hourly_rate,
        service_stations=sathi.service_stations,
        has_first_aid_certification=sathi.has_first_aid_certification,
        has_safety_training=sathi.has_safety_training
    )

@router.get("/profile/{sathi_id}", response_model=SathiProfileResponse)
async def get_sathi_profile(
    sathi_id: str,
    db: Session = Depends(get_db)
):
    """
    Get Sathi profile by ID
    """
    sathi = db.query(Sathi).filter(Sathi.id == sathi_id).first()
    if not sathi:
        raise HTTPException(status_code=404, detail="Sathi not found")
    
    return SathiProfileResponse(
        id=sathi.id,
        full_name=sathi.full_name,
        phone=sathi.phone,
        email=sathi.email,
        verification_status=sathi.verification_status,
        certification_level=sathi.certification_level,
        specializations=sathi.specializations,
        languages_spoken=sathi.languages_spoken,
        rating=sathi.rating,
        total_assignments=sathi.total_assignments,
        successful_assignments=sathi.successful_assignments,
        karma_score=sathi.karma_score,
        is_available=sathi.is_available,
        hourly_rate=sathi.hourly_rate,
        service_stations=sathi.service_stations,
        has_first_aid_certification=sathi.has_first_aid_certification,
        has_safety_training=sathi.has_safety_training
    )

@router.get("/my-profile", response_model=SathiProfileResponse)
async def get_my_sathi_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's Sathi profile
    """
    sathi = db.query(Sathi).filter(Sathi.user_id == current_user.id).first()
    if not sathi:
        raise HTTPException(status_code=404, detail="User is not registered as Sathi")
    
    return SathiProfileResponse(
        id=sathi.id,
        full_name=sathi.full_name,
        phone=sathi.phone,
        email=sathi.email,
        verification_status=sathi.verification_status,
        certification_level=sathi.certification_level,
        specializations=sathi.specializations,
        languages_spoken=sathi.languages_spoken,
        rating=sathi.rating,
        total_assignments=sathi.total_assignments,
        successful_assignments=sathi.successful_assignments,
        karma_score=sathi.karma_score,
        is_available=sathi.is_available,
        hourly_rate=sathi.hourly_rate,
        service_stations=sathi.service_stations,
        has_first_aid_certification=sathi.has_first_aid_certification,
        has_safety_training=sathi.has_safety_training
    )

# ==============================================================================
# SATHI DISCOVERY & AVAILABILITY APIs
# ==============================================================================

@router.post("/available", response_model=List[SathiProfileResponse])
async def find_available_sathis(
    request: AvailableSathiRequest,
    db: Session = Depends(get_db)
):
    """
    Find available Sathis for a given station and time
    """
    # Base query for available Sathis
    query = db.query(Sathi).filter(
        Sathi.is_available == True,
        Sathi.verification_status == SathiVerificationStatus.ACTIVE.value
    )
    
    # Filter by service stations
    if request.station_code:
        query = query.filter(
            Sathi.service_stations.cast(JSONB).contains([request.station_code])
        )
    
    # Filter by specializations
    if request.required_specializations:
        for specialization in request.required_specializations:
            query = query.filter(
                Sathi.specializations.cast(JSONB).contains([specialization])
            )
    
    # Filter by languages
    if request.required_languages:
        for language in request.required_languages:
            query = query.filter(
                Sathi.languages_spoken.cast(JSONB).contains([language])
            )
    
    # Filter by gender preference
    if request.gender_preference:
        query = query.filter(Sathi.gender == request.gender_preference)
    
    # Get results
    sathis = query.limit(20).all()
    
    return [
        SathiProfileResponse(
            id=sathi.id,
            full_name=sathi.full_name,
            phone=sathi.phone,
            email=sathi.email,
            verification_status=sathi.verification_status,
            certification_level=sathi.certification_level,
            specializations=sathi.specializations,
            languages_spoken=sathi.languages_spoken,
            rating=sathi.rating,
            total_assignments=sathi.total_assignments,
            successful_assignments=sathi.successful_assignments,
            karma_score=sathi.karma_score,
            is_available=sathi.is_available,
            hourly_rate=sathi.hourly_rate,
            service_stations=sathi.service_stations,
            has_first_aid_certification=sathi.has_first_aid_certification,
            has_safety_training=sathi.has_safety_training
        )
        for sathi in sathis
    ]

# ==============================================================================
# SATHI ASSIGNMENT APIs
# ==============================================================================

@router.post("/assign", response_model=Dict[str, Any])
async def assign_sathi_to_journey(
    request: SathiAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign Sathi to passenger journey
    """
    # Check if Sathi exists and is available
    sathi = db.query(Sathi).filter(
        Sathi.id == request.sathi_id,
        Sathi.is_available == True,
        Sathi.verification_status == SathiVerificationStatus.ACTIVE.value
    ).first()
    
    if not sathi:
        raise HTTPException(status_code=404, detail="Sathi not found or not available")
    
    # Check if Sathi is already assigned during this time
    # (Simplified check - in production would check time conflicts)
    
    # Create assignment
    assignment = SathiAssignment(
        sathi_id=request.sathi_id,
        passenger_id=current_user.id,
        journey_id=request.journey_id,
        assignment_type=request.assignment_type,
        start_station_code=request.start_station_code,
        end_station_code=request.end_station_code,
        expected_duration_minutes=request.expected_duration_minutes,
        safety_context=request.safety_context,
        family_group_id=request.family_group_id,
        status="pending"
    )
    
    db.add(assignment)
    
    # Update Sathi availability
    sathi.is_available = False
    sathi.next_available_from = datetime.utcnow() + timedelta(minutes=request.expected_duration_minutes)
    
    db.commit()
    db.refresh(assignment)
    
    logger.info(f"Sathi {sathi.full_name} assigned to journey {request.journey_id}")
    
    return {
        "success": True,
        "assignment_id": assignment.id,
        "sathi_name": sathi.full_name,
        "sathi_phone": sathi.phone,
        "status": assignment.status,
        "message": "Sathi assigned successfully. They will contact you shortly."
    }

# ==============================================================================
# FAMILY GROUP APIs
# ==============================================================================

@router.post("/family/create", response_model=Dict[str, Any])
async def create_family_group(
    request: FamilyGroupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create family group for tracking multiple travelers
    """
    # Create family group
    family_group = FamilyGroup(
        owner_id=current_user.id,
        group_name=request.group_name,
        members=[current_user.id],  # Owner is first member
        notification_preferences=request.notification_preferences or {
            "sos_alerts": True,
            "journey_updates": True,
            "checkpoint_alerts": True,
            "delay_alerts": True,
            "sathi_assignment": True
        },
        auto_share_location=request.auto_share_location,
        require_check_ins=request.require_check_ins
    )
    
    db.add(family_group)
    db.commit()
    db.refresh(family_group)
    
    logger.info(f"Family group created: {family_group.group_name} ({family_group.id})")
    
    return {
        "success": True,
        "family_group_id": family_group.id,
        "group_name": family_group.group_name,
        "owner_id": family_group.owner_id,
        "members": family_group.members,
        "message": "Family group created successfully"
    }

# ==============================================================================
# JOURNEY PLANNING APIs
# ==============================================================================

@router.post("/journey/plan", response_model=Dict[str, Any])
async def create_journey_plan(
    request: JourneyPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create journey plan with safety checkpoints
    """
    # Create journey plan
    journey_plan = JourneyPlan(
        passenger_id=current_user.id,
        family_group_id=request.family_group_id,
        journey_type=request.journey_type,
        start_station_code=request.start_station_code,
        end_station_code=request.end_station_code,
        planned_departure=request.planned_departure,
        planned_arrival=request.planned_arrival,
        route_details=request.route_details,
        pnr_numbers=request.pnr_numbers or [],
        train_numbers=request.train_numbers or [],
        safety_level=request.safety_level,
        requires_sathi=request.requires_sathi,
        sathi_preferences=request.sathi_preferences or {},
        status="planned"
    )
    
    db.add(journey_plan)
    db.commit()
    db.refresh(journey_plan)
    
    logger.info(f"Journey plan created: {journey_plan.id}")
    
    return {
        "success": True,
        "journey_plan_id": journey_plan.id,
        "status": journey_plan.status,
        "message": "Journey plan created successfully"
    }

# ==============================================================================
# HEALTH CHECK APIs
# ==============================================================================

@router.get("/health")
async def sathi_service_health(db: Session = Depends(get_db)):
    """
    Sathi service health check
    """
    try:
        # Check database connectivity
        sathi_count = db.query(Sathi).count()
        assignment_count = db.query(SathiAssignment).count()
        
        return {
            "status": "healthy",
            "sathi_count": sathi_count,
            "assignment_count": assignment_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Sathi health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }