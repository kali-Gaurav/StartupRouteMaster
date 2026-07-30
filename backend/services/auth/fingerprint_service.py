import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from database.models import IdentityFingerprint, User

logger = logging.getLogger(__name__)

class FingerprintService:
    """
    Task 45: Persona Correlation & Identity Tracking.
    Manages cryptographic device fingerprints to prevent Sybil attacks.
    """

    def generate_hash(self, components: Dict[str, Any]) -> str:
        """
        Generates a SHA-256 fingerprint from device components.
        Expected components: user_agent, screen_res, timezone, language, cpu_cores.
        """
        # Sort keys to ensure deterministic hashing
        raw_str = "|".join([f"{k}:{v}" for k, v in sorted(components.items())])
        return hashlib.sha256(raw_str.encode()).hexdigest()

    async def sync_fingerprint(self, db: Session, user_id: str, components: Dict[str, Any], ip_address: str) -> IdentityFingerprint:
        """
        Upserts a fingerprint record and performs risk calculation.
        """
        finger_hash = self.generate_hash(components)
        
        fingerprint = db.query(IdentityFingerprint).filter_by(fingerprint_hash=finger_hash).first()
        
        if not fingerprint:
            fingerprint = IdentityFingerprint(
                user_id=user_id,
                fingerprint_hash=finger_hash,
                ip_address=ip_address,
                user_agent=components.get("user_agent", "UNKNOWN"),
                first_seen_at=datetime.utcnow()
            )
            db.add(fingerprint)
        else:
            # Check for Sybil Attack (Same device, different user)
            if fingerprint.user_id != user_id:
                logger.warning(f"🚨 [PERSONA] SYBIL DETECTED: Device {finger_hash[:8]} switching users: {fingerprint.user_id} -> {user_id}")
                fingerprint.risk_score = min(1.0, fingerprint.risk_score + 0.3)
                # Link both users for shadow-ban analysis
                # (In a real system, we'd add to a Many-to-Many 'LinkedIdentities' table)
            
            fingerprint.last_seen_at = datetime.utcnow()
            fingerprint.ip_address = ip_address
            
        db.commit()
        return fingerprint

    def get_risk_score(self, db: Session, fingerprint_hash: str) -> float:
        """
        Retrieves the risk score for a specific device.
        """
        fp = db.query(IdentityFingerprint).filter_by(fingerprint_hash=fingerprint_hash).first()
        return fp.risk_score if fp else 0.0

fingerprint_service = FingerprintService()
