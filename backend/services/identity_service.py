import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request
from database.models import IdentityFingerprint, FraudAlert, User
from collections import deque
import asyncio

logger = logging.getLogger(__name__)

class IdentityService:
    """
    Project Sentinel S1: Identity & Fraud Detection.
    Handles device fingerprinting, risk scoring, and suspicious activity detection.
    
    With metrics tracking for identity and fraud detection operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("IdentityService initialized with metrics tracking")

    async def get_or_create_fingerprint(self, request: Request, user_id: Optional[str] = None) -> IdentityFingerprint:
        """
        [SENTINEL S1.5] Industrial Identity & Behavioral Profiling.
        Returns the fingerprint and a 'trust_context' for the orchestrator.
        """
        user_agent = request.headers.get("user-agent", "unknown")
        ip_address = request.client.host if request.client else "0.0.0.0"
        
        # [Task 45.1] Generate cryptographic hash
        raw_string = f"{user_agent}|{ip_address}"
        fingerprint_hash = hashlib.sha256(raw_string.encode()).hexdigest()
        
        # [Rigor] Velocity & Behavioral Entropy Checks
        behavioral_risk = await self._calculate_behavioral_risk(fingerprint_hash, request)
        await self._check_velocity(fingerprint_hash, user_id, behavioral_risk)
        
        fingerprint = self.db.query(IdentityFingerprint).filter_by(fingerprint_hash=fingerprint_hash).first()
        
        if not fingerprint:
            fingerprint = IdentityFingerprint(
                id=str(uuid.uuid4()),
                user_id=user_id,
                fingerprint_hash=fingerprint_hash,
                ip_address=ip_address,
                user_agent=user_agent,
                is_trusted=True,
                risk_score=behavioral_risk
            )
            self.db.add(fingerprint)
            logger.info(f"🆕 [SENTINEL S1.5] New identity registered: {fingerprint_hash[:10]}... (Initial Risk: {behavioral_risk})")
        else:
            fingerprint.updated_at = datetime.utcnow()
            # Gradually decay risk score if behaving well
            fingerprint.risk_score = max(0.0, (fingerprint.risk_score + behavioral_risk) / 2)
            if user_id and not fingerprint.user_id:
                fingerprint.user_id = user_id
            
        # [Audit] Check for Sybil Attack
        await self._detect_sybil_attack(fingerprint, user_id)
        
        self.db.commit()
        return fingerprint

    async def _calculate_behavioral_risk(self, fingerprint_hash: str, request: Request) -> float:
        """
        [Rigor] Entropy-based detection.
        Tracks the variety of routes searched. High entropy = Scraper.
        """
        from core.redis_client import async_redis_client
        source = request.query_params.get("source", "UNKNOWN")
        dest = request.query_params.get("destination", "UNKNOWN")
        route_key = f"{source}:{dest}"
        
        history_key = f"sentinel:history:{fingerprint_hash}"
        
        # Add current route to the recent history set (TTL 10 mins)
        await async_redis_client.sadd(history_key, route_key)
        await async_redis_client.expire(history_key, 600)
        
        distinct_routes = await async_redis_client.scard(history_key)
        
        # Entropy Logic: If user searches 10+ distinct routes in 10 mins, risk spikes.
        if distinct_routes > 10:
            return min(1.0, (distinct_routes - 10) * 0.1)
        return 0.0

    async def _check_velocity(self, fingerprint_hash: str, user_id: Optional[str], behavioral_risk: float):
        """
        Industrial Velocity Latch: Detects high-frequency requests from a single hardware ID.
        Uses Redis INCR with a sliding window.
        """
        from core.redis_client import async_redis_client
        key = f"sentinel:velocity:{fingerprint_hash}"
        
        # Increment request count for the last 60 seconds
        count = await async_redis_client.incr(key)
        if count == 1:
            await async_redis_client.expire(key, 60)
            
        # [Rigor] Multiply effective count by behavioral risk to trigger faster for scrapers
        effective_count = count * (1 + behavioral_risk * 5)
            
        if count > 20: # Threshold: 20 requests/min
            logger.warning(f"⚡ [SENTINEL:VELOCITY] High intensity detected for {fingerprint_hash[:10]}. Effective Count: {effective_count}")
            if effective_count > 50:
                # Critical breach
                if user_id:
                    await self.log_fraud_alert(user_id, "VELOCITY_EXCEEDED", "HIGH", {"count": count, "behavioral_risk": behavioral_risk})
                
                # [Rigor] Shadow Ban Logic: We don't raise Exception here, we let orchestrator handle it via risk score
                pass

    async def _detect_sybil_attack(self, fingerprint: IdentityFingerprint, current_user_id: Optional[str]):
        """
        Detects if too many distinct users are sharing the same hardware fingerprint.
        """
        if not current_user_id:
            return
            
        # Check historical users for this fingerprint
        distinct_users = self.db.query(IdentityFingerprint.user_id).filter(
            IdentityFingerprint.fingerprint_hash == fingerprint.fingerprint_hash,
            IdentityFingerprint.user_id != None
        ).distinct().count()
        
        if distinct_users > 3: # Threshold for suspicion
            logger.warning(f"🚨 [SENTINEL] Sybil Attack Suspected for fingerprint {fingerprint.fingerprint_hash[:10]}")
            await self.log_fraud_alert(
                user_id=current_user_id,
                alert_type="SYBIL_ATTACK",
                severity="HIGH",
                metadata={"distinct_users": distinct_users, "fingerprint_hash": fingerprint.fingerprint_hash}
            )
            fingerprint.risk_score = min(1.0, fingerprint.risk_score + 0.3)

    async def log_fraud_alert(self, user_id: str, alert_type: str, severity: str, metadata: Dict[str, Any]):
        """
        Logs a fraud alert for administrative review.
        """
        alert = FraudAlert(
            id=str(uuid.uuid4()),
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            status="OPEN",
            metadata_json=metadata
        )
        self.db.add(alert)
        self.db.commit()
        logger.info(f"🛡️ [SENTINEL:ALERT] {alert_type} logged for user {user_id}")

    def is_trusted_device(self, fingerprint_hash: str) -> bool:
        """
        Quick check for device trust status.
        """
        fp = self.db.query(IdentityFingerprint).filter_by(fingerprint_hash=fingerprint_hash).first()
        if not fp:
            return False
        return fp.is_trusted and fp.risk_score < 0.7

    # =========================================================================
    # METRICS TRACKING
    # =========================================================================

    async def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for identity operations."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type
        }

    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "metrics": self.get_metrics()
        }
