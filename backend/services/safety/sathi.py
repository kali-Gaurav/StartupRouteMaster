from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from database.models.sathi import Sathi, SathiIdentity, SathiVerificationStatus, SathiCertificationLevel, SathiAssignment
from database.models.core import User
from core.resilience.core import circuit_manager
from services.multi_layer_cache import multi_layer_cache
import orjson as json
import math

if TYPE_CHECKING:
    from database.models.sathi import SathiAssignment

logger = logging.getLogger(__name__)

class SathiService:
    """
    Sathi (Safety Guide) Management Service
    Handles onboarding, KYC verification, and assignment
    """

    def __init__(self, db: Session):
        self.db = db
        self._verification_breaker = circuit_manager.get_breaker("sathi_verification")

    def create_sathi_profile(self, user_id: str, full_name: str, phone: str, email: Optional[str] = None) -> Sathi:
        """Initialize a new Sathi profile in PENDING status"""
        existing = self.db.query(Sathi).filter(Sathi.user_id == user_id).first()
        if existing:
            raise ValueError(f"Sathi profile already exists for user {user_id}")

        sathi = Sathi(
            id=str(uuid.uuid4()),
            user_id=user_id,
            full_name=full_name,
            phone=phone,
            email=email,
            verification_status=SathiVerificationStatus.PENDING.value,
            is_available=False # Start unavailable until verified
        )
        self.db.add(sathi)
        self.db.commit()
        self.db.refresh(sathi)
        return sathi

    async def submit_kyc(
        self, 
        sathi_id: str, 
        aadhar_hash: str, 
        encrypted_aadhar: bytes, 
        encryption_iv: bytes,
        uidai_ref: Optional[str] = None
    ) -> SathiIdentity:
        """[Task 1.1] Submit encrypted KYC data and trigger state transition"""
        sathi = self.db.query(Sathi).filter(Sathi.id == sathi_id).first()
        if not sathi:
            raise ValueError(f"Sathi {sathi_id} not found")

        # Validate State Transition (PENDING -> SUBMITTED)
        if not sathi.can_transition_to(SathiVerificationStatus.SUBMITTED):
            raise ValueError(f"Cannot submit KYC from status {sathi.verification_status}")

        # [Industrial Logic] Link to the specialized KYC Service for audit & verification
        from services.kyc_service import KYCService
        await KYCService.submit_for_verification(sathi_id, "AADHAAR", aadhar_hash)

        identity = SathiIdentity(
            id=str(uuid.uuid4()),
            sathi_id=sathi_id,
            aadhar_hash=aadhar_hash,
            encrypted_aadhar_number=encrypted_aadhar,
            encryption_iv=encryption_iv,
            uidai_reference_id=uidai_ref
        )
        
        sathi.verification_status = SathiVerificationStatus.SUBMITTED.value
        self.db.add(identity)
        self.db.commit()
        self.db.refresh(identity)
        
        from core.infrastructure.metrics import jit_metrics
        jit_metrics.sathi_onboarded += 1
        
        return identity

    async def auto_verify_kyc(self, sathi_id: str):
        """[Task RM-S-002] Automated background check simulation for Sathi onboarding"""
        sathi = self.db.query(Sathi).filter(Sathi.id == sathi_id).first()
        if not sathi:
            return

        # Sequential transitions for simulation
        transitions = [
            (SathiVerificationStatus.KYC_COMPLETE, "background_check_date"),
            (SathiVerificationStatus.POLICE_VERIFIED, "police_verification_date"),
            (SathiVerificationStatus.TRAINING_COMPLETE, "training_completion_date"),
            (SathiVerificationStatus.ACTIVE, "activation_date")
        ]

        for status, date_field in transitions:
            sathi.verification_status = status.value
            setattr(sathi, date_field, datetime.utcnow())
            if status == SathiVerificationStatus.ACTIVE:
                sathi.is_available = True
            self.db.commit()
            logger.info(f"SATHI_VERIFICATION | {sathi_id} transitioned to {status.value}")
            
        return sathi

    def get_sathi_by_user_id(self, user_id: str) -> Optional[Sathi]:
        """[Task RM-S-004] Retrieve Sathi profile by associated user_id"""
        return self.db.query(Sathi).filter(Sathi.user_id == user_id).first()

    def update_verification_status(
        self, 
        sathi_id: str, 
        next_status: SathiVerificationStatus, 
        admin_id: Optional[str] = None
    ) -> Sathi:
        """[Task 1.2] Strict State Machine Update"""
        sathi = self.db.query(Sathi).filter(Sathi.id == sathi_id).first()
        if not sathi:
            raise ValueError(f"Sathi {sathi_id} not found")

        if not sathi.can_transition_to(next_status):
            raise ValueError(f"Invalid transition from {sathi.verification_status} to {next_status.value}")

        sathi.verification_status = next_status.value
        
        from core.infrastructure.metrics import jit_metrics
        # Side effects of activation
        if next_status == SathiVerificationStatus.ACTIVE:
            sathi.activation_date = datetime.utcnow()
            sathi.is_available = True
            jit_metrics.sathi_active += 1
            
        # Update dates based on status
        if next_status == SathiVerificationStatus.KYC_COMPLETE:
            sathi.background_check_date = datetime.utcnow()
        elif next_status == SathiVerificationStatus.POLICE_VERIFIED:
            sathi.police_verification_date = datetime.utcnow()
        elif next_status == SathiVerificationStatus.TRAINING_COMPLETE:
            sathi.training_completion_date = datetime.utcnow()

        self.db.commit()
        self.db.refresh(sathi)
        return sathi

    def find_available_sathis(
        self, 
        station_code: str, 
        specialization: Optional[str] = None
    ) -> List[Sathi]:
        """Find active and available Sathis near a station"""
        from sqlalchemy import cast, String
        query = self.db.query(Sathi).filter(
            Sathi.verification_status == SathiVerificationStatus.ACTIVE.value,
            Sathi.is_available == True,
            cast(Sathi.service_stations, String).contains(f'"{station_code}"')
        )
        
        if specialization:
            query = query.filter(Sathi.specializations.contains([specialization]))
            
        return query.order_by(Sathi.rating.desc()).all()

    def get_nearby_sathi_locations(self, lat: float, lng: float, radius_km: float = 50.0) -> List[Dict[str, Any]]:
        """Find active Sathis within a certain radius using Haversine approximation"""
        # Bounding box for pre-filtering
        lat_delta = radius_km / 111.0
        # Handle division by zero at poles if necessary, but for India it's fine
        cos_lat = math.cos(math.radians(lat))
        lng_delta = radius_km / (111.0 * abs(cos_lat)) if abs(cos_lat) > 0.01 else radius_km / 1.0
        
        query = self.db.query(Sathi).filter(
            Sathi.verification_status == SathiVerificationStatus.ACTIVE.value,
            Sathi.is_available == True,
            Sathi.current_lat.between(lat - lat_delta, lat + lat_delta),
            Sathi.current_lng.between(lng - lng_delta, lng + lng_delta)
        )
        
        sathis = query.all()
        results = []
        for s in sathis:
            if s.current_lat is not None and s.current_lng is not None:
                results.append({
                    "id": s.id,
                    "name": s.full_name,
                    "lat": s.current_lat,
                    "lng": s.current_lng,
                    "rating": s.rating,
                    "specializations": s.specializations
                    # Phone masked for public map privacy (Task RM-S-003)
                })
        return results

    def get_sathi_by_user_id(self, user_id: str) -> Optional[Sathi]:
        return self.db.query(Sathi).filter(Sathi.user_id == user_id).first()

    def request_sathi_assignment(
        self, 
        passenger_id: str, 
        start_station: str, 
        end_station: str,
        context: Optional[Dict] = None
    ) -> SathiAssignment:
        """[Task 1.3] Request a Sathi for a journey"""
        from core.infrastructure.metrics import jit_metrics
        
        assignment = SathiAssignment(
            id=str(uuid.uuid4()),
            passenger_id=passenger_id,
            start_station_code=start_station,
            end_station_code=end_station,
            status="pending",
            safety_context=context or {},
            requested_at=datetime.utcnow()
        )
        
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        
        jit_metrics.sathi_assignments_total += 1
        logger.info(f"SATHI_REQUEST | Passenger {passenger_id} at {start_station}")
        
        # In a real system, this would trigger an async broadcast to nearby Sathis
        return assignment

    def accept_assignment(self, assignment_id: str, sathi_id: str) -> SathiAssignment:
        """Sathi accepts a pending assignment"""
        assignment = self.db.query(SathiAssignment).filter(SathiAssignment.id == assignment_id).first()
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        if assignment.status != "pending":
            raise ValueError(f"Assignment {assignment_id} is already {assignment.status}")
            
        sathi = self.db.query(Sathi).filter(Sathi.id == sathi_id).first()
        if not sathi or sathi.verification_status != SathiVerificationStatus.ACTIVE.value:
            raise ValueError(f"Sathi {sathi_id} is not active")

        assignment.sathi_id = sathi_id
        assignment.status = "accepted"
        assignment.accepted_at = datetime.utcnow()
        
        # Mark sathi as busy
        sathi.is_available = False
        
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    async def get_active_sathi_counts(self) -> Dict[str, int]:
        """[Task RM-007] Get a map of station_code -> count of active available Sathis (Cached)"""
        cache_key = "sathi:active_counts"
        
        # 1. Try Cache
        cached = await multi_layer_cache.get(cache_key)
        if cached:
            return cast(Dict[str, int], cached)

        # 2. Database Fetch
        from collections import defaultdict
        
        sathis = self.db.query(Sathi).filter(
            Sathi.verification_status == SathiVerificationStatus.ACTIVE.value,
            Sathi.is_available == True
        ).all()
        
        counts = defaultdict(int)
        for s in sathis:
            if s.service_stations:
                for station in s.service_stations:
                    counts[station] += 1
        
        result = dict(counts)
        
        # 3. Store Cache (5m TTL)
        await multi_layer_cache.put(cache_key, result, ttl=300)
        
        return result
