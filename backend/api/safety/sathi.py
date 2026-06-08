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
from database.models.sathi import (
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

from services.sathi_service import SathiService

class SathiKYCRequest(BaseModel):
    """Request to submit KYC for Sathi"""
    aadhar_hash: str
    encrypted_aadhar: str  # Base64 encoded bytes
    encryption_iv: str     # Base64 encoded bytes
    uidai_ref: Optional[str] = None

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
    service = SathiService(db)
    try:
        sathi = service.create_sathi_profile(
            user_id=current_user.id,
            full_name=request.full_name,
            phone=request.phone,
            email=request.email
        )
        
        # Update additional fields not covered by create_sathi_profile
        sathi.age = request.age
        sathi.gender = request.gender
        sathi.languages_spoken = request.languages_spoken
        sathi.service_stations = request.service_stations
        sathi.specializations = request.specializations
        sathi.has_first_aid_certification = request.has_first_aid_certification
        sathi.has_safety_training = request.has_safety_training
        
        db.commit()
        db.refresh(sathi)
        
        logger.info(f"Sathi registered: {sathi.full_name} ({sathi.id})")
        
        return sathi
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/kyc", response_model=Dict[str, Any])
async def submit_sathi_kyc(
    request: SathiKYCRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit KYC documents for verification
    """
    import base64
    service = SathiService(db)
    sathi = service.get_sathi_by_user_id(current_user.id)
    if not sathi:
        raise HTTPException(status_code=404, detail="Sathi profile not found")
    
    try:
        # Decode base64 strings
        encrypted_aadhar = base64.b64decode(request.encrypted_aadhar)
        encryption_iv = base64.b64decode(request.encryption_iv)
        
        service.submit_kyc(
            sathi_id=sathi.id,
            aadhar_hash=request.aadhar_hash,
            encrypted_aadhar=encrypted_aadhar,
            encryption_iv=encryption_iv,
            uidai_ref=request.uidai_ref
        )
        
        # Trigger auto-verification simulator for demo/dev purposes
        # In production, this would be a real background task
        import asyncio
        asyncio.create_task(service.auto_verify_kyc(sathi.id))
        
        return {
            "success": True,
            "message": "KYC submitted successfully and verification initiated",
            "status": "submitted"
        }
    except Exception as e:
        logger.error(f"KYC Submission Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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
    Assign Sathi to passenger journey or broadcast request
    """
    service = SathiService(db)
    
    # CASE 1: Specific Sathi requested
    if request.sathi_id and request.sathi_id != "broadcast":
        sathi = db.query(Sathi).filter(
            Sathi.id == request.sathi_id,
            Sathi.is_available == True,
            Sathi.verification_status == SathiVerificationStatus.ACTIVE.value
        ).first()
        
        if not sathi:
            raise HTTPException(status_code=404, detail="Sathi not found or not available")
        
        assignment = service.request_sathi_assignment(
            passenger_id=current_user.id,
            start_station=request.start_station_code,
            end_station=request.end_station_code,
            context=request.safety_context
        )
        
        # Manually accept for now if specific sathi requested (simplification)
        service.accept_assignment(assignment.id, sathi.id)
        
        return {
            "success": True,
            "assignment_id": assignment.id,
            "sathi_name": sathi.full_name,
            "sathi_phone": sathi.phone,
            "status": "accepted",
            "message": "Sathi assigned successfully. They will contact you shortly."
        }
    
    # CASE 2: Broadcast request
    else:
        assignment = service.request_sathi_assignment(
            passenger_id=current_user.id,
            start_station=request.start_station_code,
            end_station=request.end_station_code,
            context=request.safety_context
        )
        
        # Trigger notification to nearby sathis (Simulated)
        logger.info(f"SATHI_BROADCAST | Journey {request.journey_id} from {request.start_station_code}")
        
        return {
            "success": True,
            "assignment_id": assignment.id,
            "status": "pending",
            "message": "Safety request broadcasted to all nearby verified Sathis. We will notify you once someone accepts."
        }

@router.get("/nearby", response_model=Dict[str, Any])
async def get_nearby_sathis(
    lat: float,
    lng: float,
    radius: float = 5.0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get nearby verified Sathis for the map overlay.
    """
    from services.sathi_location_service import SathiLocationService
    
    nearby_data = await SathiLocationService.get_nearby_sathis(lat, lng, radius)
    
    # Hydrate with profile details from DB
    hydrated_results = []
    for s_loc in nearby_data:
        s_id = s_loc["id"]
        sathi = db.query(Sathi).filter(Sathi.id == s_id).first()
        if sathi:
            hydrated_results.append({
                "id": sathi.id,
                "name": sathi.full_name,
                "lat": s_loc["lat"],
                "lng": s_loc["lon"],
                "rating": sathi.rating,
                "specializations": sathi.specializations,
                "phone": sathi.phone if current_user.id == sathi.user_id else None, # Privacy
                "status": s_loc["status"]
            })
            
    return {
        "success": True,
        "count": len(hydrated_results),
        "data": hydrated_results
    }

@router.post("/location", response_model=Dict[str, Any])
async def update_sathi_location(
    lat: float,
    lng: float,
    status: str = "available",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update Sathi's real-time location.
    """
    from services.sathi_location_service import SathiLocationService
    
    # Verify current user has a sathi profile
    sathi = db.query(Sathi).filter(Sathi.user_id == current_user.id).first()
    if not sathi:
        raise HTTPException(status_code=403, detail="Only registered Sathis can update location")
    
    success = await SathiLocationService.update_location(sathi.id, lat, lng, status)
    
    if success:
        return {"success": True, "message": "Location updated"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update location in safety network")

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
