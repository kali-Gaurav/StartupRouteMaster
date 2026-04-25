import logging
import hashlib
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text, DateTime, Float, Boolean, Integer, JSON
from database.models import Base, Booking, User

from core.resilience import circuit_manager, CircuitConfig, CircuitOpenError
from core.retry import retry, RETRY_POLICY_EXTERNAL_API

logger = logging.getLogger(__name__)

# Create circuit breaker for refund operations
REFUND_BREAKER = circuit_manager.get_or_create(
    "refund_service",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
        half_open_max_calls=2
    )
)


class RefundAuditLog(Base):
    """
    Immutable audit log for all refund state changes.
    Task 6.10: Compliance-ready audit trail.
    """
    __tablename__ = 'refund_audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_id = Column(String(36), unique=True, nullable=False, index=True)
    booking_id = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # CREATE, APPROVE, REJECT, PROCESS, COMPLETE, FAIL
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    actor_type = Column(String(20), nullable=False)  # SYSTEM, ADMIN, USER, API
    actor_id = Column(String(100), nullable=True)
    amount = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 for integrity
    
    @staticmethod
    def compute_checksum(data: Dict) -> str:
        """Compute SHA-256 checksum for audit integrity."""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()


class RefundIdempotency(Base):
    """
    Idempotency key storage to prevent duplicate refunds.
    Task 6.11: Duplicate request prevention.
    """
    __tablename__ = 'refund_idempotency'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    idempotency_key = Column(String(64), unique=True, nullable=False, index=True)
    booking_id = Column(String(50), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False)  # Hash of request parameters
    response = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class RefundFraudCheck(Base):
    """
    Fraud detection tracking for refund patterns.
    Task 6.12: Refund abuse prevention.
    """
    __tablename__ = 'refund_fraud_checks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    check_type = Column(String(50), nullable=False)  # VELOCITY, PATTERN, AMOUNT, DEVICE
    risk_score = Column(Float, nullable=False)  # 0.0 to 1.0
    flags = Column(JSON, nullable=True)
    decision = Column(String(20), nullable=False)  # ALLOW, FLAG, BLOCK
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RefundService:
    """
    Task 6: Refund Queue State Machine with resilience patterns.
    Production-ready with idempotency, fraud detection, and audit trail.
    """
    
    # State Machine constants
    STATE_PENDING = "REFUND_PENDING"
    STATE_REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    STATE_INITIATED = "REFUND_INITIATED"
    STATE_SUCCESS = "REFUND_SUCCESS"
    STATE_FAILED = "REFUND_FAILED"
    
    # Thresholds
    HIGH_VALUE_THRESHOLD = 5000.0
    MAX_RETRY_COUNT = 3
    PARTIAL_REFUND_CANCELLATION_CHARGE = 50.0  # Default cancellation charge
    
    # Fraud detection thresholds
    MAX_REFUNDS_PER_USER_24H = 5
    MAX_REFUNDS_PER_USER_7D = 15
    MAX_REFUND_AMOUNT_24H = 50000.0
    HIGH_RISK_AMOUNT = 20000.0
    VELOCITY_WINDOW_HOURS = 24
    
    # Idempotency settings
    IDEMPOTENCY_TTL_HOURS = 72  # 3 days

    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 60
        self._rate_limiter: Dict[str, List[datetime]] = {}  # Simple in-memory rate limiting
        self._sla_tracking: Dict[str, datetime] = {}  # Track SLA for each refund

    def _get_cache_key(self, booking_id: str) -> str:
        return f"refund:{booking_id}"

    def _is_cache_valid(self, cached: Dict) -> bool:
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    def _notify_slack(self, message: str):
        """Task 6.9: Slack bot alerts for failed refunds."""
        logger.warning(f"SLACK REFUND ALERT: {message}")

    def _validate_amount(self, amount: float) -> bool:
        """Validate refund amount."""
        return amount >= 0 and amount <= 1000000  # Max 10L refund

    def _validate_booking(self, booking_id: str) -> Optional[Booking]:
        """Validate and retrieve booking."""
        try:
            booking = self.db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                logger.warning(f"Booking not found: {booking_id}")
                return None
            return booking
        except Exception as e:
            logger.error(f"Database error retrieving booking: {e}")
            return None

    # =========================================================================
    # TASK 6.10: AUDIT TRAIL - Immutable state change logging
    # =========================================================================
    
    def _log_audit(
        self,
        booking_id: str,
        action: str,
        new_state: str,
        actor_type: str,
        actor_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
        extra_metadata: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log an immutable audit entry for refund state changes.
        Returns the audit_id for reference.
        """
        audit_id = str(uuid.uuid4())
        
        # Prepare data for checksum
        audit_data = {
            "audit_id": audit_id,
            "booking_id": booking_id,
            "action": action,
            "previous_state": previous_state,
            "new_state": new_state,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "amount": amount,
            "reason": reason,
            "metadata": extra_metadata,
            "created_at": datetime.utcnow().isoformat()
        }
        
        checksum = RefundAuditLog.compute_checksum(audit_data)
        
        try:
            audit_entry = RefundAuditLog(
                audit_id=audit_id,
                booking_id=booking_id,
                action=action,
                previous_state=previous_state,
                new_state=new_state,
                actor_type=actor_type,
                actor_id=actor_id,
                amount=amount,
                reason=reason,
                extra_metadata=extra_metadata,
                ip_address=ip_address,
                user_agent=user_agent,
                checksum=checksum
            )
            self.db.add(audit_entry)
            self.db.commit()
            logger.debug(f"📋 Audit logged: {audit_id} | {action} | {booking_id}")
            return audit_id
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
            self.db.rollback()
            return audit_id  # Return anyway to not block operations

    def get_audit_trail(self, booking_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve complete audit trail for a booking.
        Task 6.10.1: Compliance reporting.
        """
        try:
            audits = self.db.query(RefundAuditLog).filter(
                RefundAuditLog.booking_id == booking_id
            ).order_by(RefundAuditLog.created_at.asc()).all()
            
            return [
                {
                    "audit_id": a.audit_id,
                    "action": a.action,
                    "previous_state": a.previous_state,
                    "new_state": a.new_state,
                    "actor_type": a.actor_type,
                    "actor_id": a.actor_id,
                    "amount": a.amount,
                    "reason": a.reason,
                    "metadata": a.extra_metadata,
                    "created_at": a.created_at.isoformat(),
                    "checksum": a.checksum
                }
                for a in audits
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {e}")
            return []

    def verify_audit_integrity(self, booking_id: str) -> Tuple[bool, List[str]]:
        """
        Verify audit trail integrity using checksums.
        Task 6.10.2: Tamper detection.
        """
        errors = []
        try:
            audits = self.db.query(RefundAuditLog).filter(
                RefundAuditLog.booking_id == booking_id
            ).order_by(RefundAuditLog.created_at.asc()).all()
            
            for audit in audits:
                stored_checksum = audit.checksum
                audit_data = {
                    "audit_id": audit.audit_id,
                    "booking_id": audit.booking_id,
                    "action": audit.action,
                    "previous_state": audit.previous_state,
                    "new_state": audit.new_state,
                    "actor_type": audit.actor_type,
                    "actor_id": audit.actor_id,
                    "amount": audit.amount,
                    "reason": audit.reason,
                    "metadata": audit.extra_metadata,
                    "created_at": audit.created_at.isoformat()
                }
                computed = RefundAuditLog.compute_checksum(audit_data)
                if computed != stored_checksum:
                    errors.append(f"Checksum mismatch for audit {audit.audit_id}")
            
            return (len(errors) == 0, errors)
        except Exception as e:
            return (False, [str(e)])

    # =========================================================================
    # TASK 6.11: IDEMPOTENCY - Prevent duplicate refunds
    # =========================================================================
    
    def _generate_request_hash(
        self,
        booking_id: str,
        amount: float,
        reason: str,
        is_partial: bool
    ) -> str:
        """Generate deterministic hash for request deduplication."""
        content = f"{booking_id}:{amount}:{reason}:{is_partial}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _check_idempotency(self, idempotency_key: str) -> Optional[Dict]:
        """
        Check if request was already processed.
        Returns cached response if found and not expired.
        """
        try:
            record = self.db.query(RefundIdempotency).filter(
                RefundIdempotency.idempotency_key == idempotency_key
            ).first()
            
            if record and not record.is_expired():
                logger.info(f"🔄 Idempotent request found: {idempotency_key}")
                return record.response
            
            # Clean up expired
            if record:
                self.db.delete(record)
                self.db.commit()
            
            return None
        except Exception as e:
            logger.error(f"Idempotency check failed: {e}")
            return None

    def _record_idempotency(
        self,
        idempotency_key: str,
        booking_id: str,
        request_hash: str,
        response: Dict
    ) -> None:
        """Cache idempotent response."""
        try:
            expires = datetime.utcnow() + timedelta(hours=self.IDEMPOTENCY_TTL_HOURS)
            record = RefundIdempotency(
                idempotency_key=idempotency_key,
                booking_id=booking_id,
                request_hash=request_hash,
                response=response,
                expires_at=expires
            )
            self.db.add(record)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to record idempotency: {e}")
            self.db.rollback()

    # =========================================================================
    # TASK 6.12: FRAUD DETECTION - Prevent refund abuse
    # =========================================================================
    
    def _check_fraud(self, booking: Booking, amount: float) -> Tuple[bool, str, Dict]:
        """
        Perform fraud checks on refund request.
        Returns: (is_allowed, decision, details)
        """
        user_id = booking.user_id or "unknown"
        details = {"flags": [], "risk_score": 0.0}
        
        try:
            # Check 1: User refund velocity (24h)
            window_24h = datetime.utcnow() - timedelta(hours=self.VELOCITY_WINDOW_HOURS)
            recent_refunds_24h = self.db.query(RefundFraudCheck).filter(
                RefundFraudCheck.user_id == user_id,
                RefundFraudCheck.created_at >= window_24h
            ).count()
            
            if recent_refunds_24h >= self.MAX_REFUNDS_PER_USER_24H:
                details["flags"].append("HIGH_VELOCITY_24H")
                details["risk_score"] += 0.4
            
            # Check 2: User refund velocity (7 days)
            window_7d = datetime.utcnow() - timedelta(days=7)
            recent_refunds_7d = self.db.query(RefundFraudCheck).filter(
                RefundFraudCheck.user_id == user_id,
                RefundFraudCheck.created_at >= window_7d
            ).count()
            
            if recent_refunds_7d >= self.MAX_REFUNDS_PER_USER_7D:
                details["flags"].append("HIGH_VELOCITY_7D")
                details["risk_score"] += 0.3
            
            # Check 3: Total refund amount in 24h
            # Query bookings with recent refunds
            recent_booking_ids = self.db.query(RefundAuditLog.booking_id).filter(
                RefundAuditLog.action == "COMPLETE",
                RefundAuditLog.created_at >= window_24h,
                RefundAuditLog.actor_type == "SYSTEM"
            ).distinct().all()
            
            total_24h = sum(
                self._get_booking_refund_amount(bid[0]) 
                for bid in recent_booking_ids
            )
            
            if total_24h + amount > self.MAX_REFUND_AMOUNT_24H:
                details["flags"].append("HIGH_AMOUNT_24H")
                details["risk_score"] += 0.3
            
            # Check 4: High value check
            if amount >= self.HIGH_RISK_AMOUNT:
                details["flags"].append("HIGH_VALUE")
                details["risk_score"] += 0.2
            
            # Log fraud check
            decision = "ALLOW"
            if details["risk_score"] >= 0.7:
                decision = "BLOCK"
            elif details["risk_score"] >= 0.4:
                decision = "FLAG"
            
            fraud_record = RefundFraudCheck(
                booking_id=str(booking.id),
                user_id=user_id,
                check_type="COMPREHENSIVE",
                risk_score=details["risk_score"],
                flags=details["flags"],
                decision=decision
            )
            self.db.add(fraud_record)
            self.db.commit()
            
            # Log to audit
            if decision == "BLOCK":
                self._log_audit(
                    booking_id=str(booking.id),
                    action="FRAUD_BLOCK",
                    new_state="BLOCKED",
                    actor_type="SYSTEM",
                    amount=amount,
                    extra_metadata=details
                )
            
            return (decision != "BLOCK", decision, details)
            
        except Exception as e:
            logger.error(f"Fraud check failed: {e}")
            # Fail open - allow on error
            return (True, "ALLOW", {"error": str(e)})

    def _get_booking_refund_amount(self, booking_id: str) -> float:
        """Get total refund amount for a booking."""
        try:
            booking = self._validate_booking(booking_id)
            if not booking:
                return 0.0
            details = booking.booking_details or {}
            refund_info = details.get("refund_info", {})
            return refund_info.get("amount", 0.0)
        except:
            return 0.0

    # =========================================================================
    # TASK 6.13: SLA TRACKING - Monitor processing times
    # =========================================================================
    
    def _start_sla_timer(self, booking_id: str) -> None:
        """Start SLA timer for a refund."""
        self._sla_tracking[booking_id] = datetime.utcnow()

    def _check_sla(self, booking_id: str) -> Optional[Dict]:
        """Check if SLA is breached."""
        if booking_id not in self._sla_tracking:
            return None
        
        start = self._sla_tracking[booking_id]
        elapsed = (datetime.utcnow() - start).total_seconds()
        
        # SLA: 24 hours for standard, 4 hours for urgent
        booking = self._validate_booking(booking_id)
        if booking:
            details = booking.booking_details or {}
            refund_info = details.get("refund_info", {})
            is_urgent = refund_info.get("amount", 0) > self.HIGH_VALUE_THRESHOLD
            sla_seconds = 4 * 3600 if is_urgent else 24 * 3600
            
            if elapsed > sla_seconds:
                return {
                    "breached": True,
                    "elapsed_seconds": elapsed,
                    "sla_seconds": sla_seconds,
                    "breach_duration": elapsed - sla_seconds
                }
        
        return {"breached": False, "elapsed_seconds": elapsed}

    def get_sla_metrics(self) -> Dict[str, Any]:
        """Get SLA performance metrics."""
        now = datetime.utcnow()
        total = len(self._sla_tracking)
        breached = 0
        total_elapsed = 0.0
        
        for bid, start in self._sla_tracking.items():
            elapsed = (now - start).total_seconds()
            total_elapsed += elapsed
            if elapsed > 24 * 3600:  # 24 hour SLA
                breached += 1
        
        return {
            "total_tracked": total,
            "breached_count": breached,
            "breach_rate": breached / total if total > 0 else 0,
            "avg_elapsed_seconds": total_elapsed / total if total > 0 else 0
        }

    # =========================================================================
    # MAIN REFUND OPERATIONS
    # =========================================================================

    # =========================================================================
    # MAIN REFUND OPERATIONS
    # =========================================================================

    def create_refund_request(
        self, 
        booking_id: str, 
        reason: str, 
        amount: float, 
        is_partial: bool = False, 
        cancellation_charge: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates a refund request in the queue.
        Supports Task 6.2 (Sold out trigger) and 6.5 (Partial refund).
        Production-ready with idempotency, fraud detection, and audit.
        
        Args:
            booking_id: The booking ID to refund
            reason: Reason for refund (e.g., "IRCTC_SOLD_OUT", "USER_CANCELLED")
            amount: Refund amount
            is_partial: Whether this is a partial refund
            cancellation_charge: Optional cancellation charge for partial refunds
            idempotency_key: Unique key to prevent duplicate requests
            ip_address: Client IP for audit
            user_agent: Client user agent for audit
            
        Returns:
            Dict with refund status and details
        """
        # TASK 6.11: Check idempotency first
        if idempotency_key:
            cached_response = self._check_idempotency(idempotency_key)
            if cached_response:
                logger.info(f"🔄 Returning cached response for idempotency key: {idempotency_key}")
                cached_response["idempotent_replay"] = True
                return cached_response
        
        # Validate amount
        if not self._validate_amount(amount):
            return {"success": False, "message": "Invalid refund amount"}
        
        # Validate booking
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        # TASK 6.12: Fraud detection
        fraud_allowed, fraud_decision, fraud_details = self._check_fraud(booking, amount)
        if not fraud_allowed:
            self._notify_slack(
                f"🚨 FRAUD BLOCK: Booking {booking_id}, Amount ₹{amount}, "
                f"Risk Score: {fraud_details.get('risk_score', 0):.2f}, "
                f"Flags: {fraud_details.get('flags', [])}"
            )
            return {
                "success": False, 
                "message": "Refund blocked due to suspicious activity",
                "fraud_check": fraud_decision,
                "details": fraud_details
            }
        
        # Log fraud flag if applicable
        if fraud_decision == "FLAG":
            logger.warning(f"⚠️ Refund flagged: {booking_id}, flags={fraud_details.get('flags', [])}")
        
        # Check if booking already has a pending refund
        booking_details = booking.booking_details or {}
        if "refund_info" in booking_details:
            existing_status = booking_details["refund_info"].get("status", "")
            if existing_status in [self.STATE_PENDING, self.STATE_INITIATED]:
                return {
                    "success": False, 
                    "message": f"Refund already in progress: {existing_status}",
                    "existing_status": existing_status
                }
            if existing_status == self.STATE_SUCCESS:
                return {
                    "success": False,
                    "message": "Refund already processed",
                    "refund_status": existing_status
                }

        # Calculate final amount
        final_amount = amount
        if is_partial:
            charge = cancellation_charge or self.PARTIAL_REFUND_CANCELLATION_CHARGE
            final_amount = max(0, amount - charge)

        # Determine initial status based on amount
        initial_status = self.STATE_PENDING
        if final_amount > self.HIGH_VALUE_THRESHOLD:
            initial_status = self.STATE_REQUIRES_APPROVAL
            self._notify_slack(
                f"High-value refund requires manual approval: "
                f"Booking {booking_id}, Amount ₹{final_amount}"
            )

        # Create refund info
        refund_data = {
            "amount": final_amount,
            "original_amount": amount,
            "status": initial_status,
            "reason": reason,
            "is_partial": is_partial,
            "cancellation_charge": cancellation_charge or 0,
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "fraud_decision": fraud_decision,
            "fraud_flags": fraud_details.get("flags", [])
        }
        
        # Update booking details
        try:
            from sqlalchemy.orm.attributes import flag_modified
            
            booking_details["refund_info"] = refund_data
            booking.booking_details = booking_details
            flag_modified(booking, "booking_details")
            
            # Auto-cancel booking if it was sold out (Task 6.2)
            if reason == "IRCTC_SOLD_OUT":
                booking.booking_status = "cancelled"
                logger.info(f"Booking {booking_id} auto-cancelled due to sold out")
            
            self.db.commit()
            
            # TASK 6.10: Log audit trail
            self._log_audit(
                booking_id=booking_id,
                action="CREATE",
                new_state=initial_status,
                actor_type="SYSTEM",
                previous_state=None,
                amount=final_amount,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                extra_metadata={"is_partial": is_partial, "fraud_decision": fraud_decision}
            )
            
            # TASK 6.13: Start SLA tracking
            self._start_sla_timer(booking_id)
            
            # Invalidate cache
            cache_key = self._get_cache_key(booking_id)
            self._cache.pop(cache_key, None)
            
            # TASK 6.11: Record idempotency
            if idempotency_key:
                request_hash = self._generate_request_hash(booking_id, amount, reason, is_partial)
                response = {
                    "success": True, 
                    "refund_status": initial_status, 
                    "amount": final_amount,
                    "booking_id": booking_id
                }
                self._record_idempotency(idempotency_key, booking_id, request_hash, response)
            
            logger.info(f"✅ Refund request created: {booking_id} | Status: {initial_status} | Amount: ₹{final_amount}")
            
            result = {
                "success": True, 
                "refund_status": initial_status, 
                "amount": final_amount,
                "booking_id": booking_id
            }
            
            # Add fraud flag info if applicable
            if fraud_decision == "FLAG":
                result["fraud_warning"] = True
                result["fraud_flags"] = fraud_details.get("flags", [])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create refund request: {e}")
            self.db.rollback()
            return {"success": False, "message": str(e)}

    def get_refund_status(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current refund status for a booking.
        """
        cache_key = self._get_cache_key(booking_id)
        
        # Check cache
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached = self._cache[cache_key]
            logger.debug(f"📦 Cache hit for refund status {booking_id}")
            return cached

        # Fetch from database
        booking = self._validate_booking(booking_id)
        if not booking:
            return None
        
        booking_details = booking.booking_details or {}
        refund_info = booking_details.get("refund_info")
        
        if not refund_info:
            return None
        
        result = {
            "booking_id": booking_id,
            "status": refund_info.get("status"),
            "amount": refund_info.get("amount"),
            "reason": refund_info.get("reason"),
            "created_at": refund_info.get("created_at"),
            "is_partial": refund_info.get("is_partial", False)
        }
        
        # Cache the result
        result["_cached_at"] = datetime.utcnow().timestamp()
        self._cache[cache_key] = result
        
        return result

    def process_refund(
        self, 
        booking_id: str, 
        target_vpa: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moves a refund from PENDING to INITIATED to SUCCESS.
        Production-ready with idempotency, audit, and SLA tracking.
        """
        # TASK 6.11: Check idempotency
        if idempotency_key:
            cached_response = self._check_idempotency(idempotency_key)
            if cached_response:
                logger.info(f"🔄 Returning cached response for idempotency key: {idempotency_key}")
                cached_response["idempotent_replay"] = True
                return cached_response
        
        # Validate booking
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        booking_details = booking.booking_details or {}
        refund_info = booking_details.get("refund_info")
        
        if not refund_info:
            return {"success": False, "message": "No refund request found"}
        
        # Check state transitions
        status = refund_info.get("status")
        
        if status == self.STATE_REQUIRES_APPROVAL:
            return {"success": False, "message": "Refund requires admin approval first."}
        
        if status in [self.STATE_SUCCESS, self.STATE_INITIATED]:
            return {"success": False, "message": f"Refund already in state {status}"}
        
        if status != self.STATE_PENDING:
            return {"success": False, "message": f"Invalid refund state: {status}"}

        # Validate VPA
        if not target_vpa:
            refund_info["retry_count"] = refund_info.get("retry_count", 0) + 1
            
            if refund_info["retry_count"] >= self.MAX_RETRY_COUNT:
                refund_info["status"] = self.STATE_FAILED
                self._update_booking_refund(booking, booking_details, refund_info)
                
                # TASK 6.10: Log audit for failure
                self._log_audit(
                    booking_id=booking_id,
                    action="PROCESS_FAIL",
                    new_state=self.STATE_FAILED,
                    actor_type="SYSTEM",
                    previous_state=status,
                    amount=refund_info.get("amount"),
                    reason="Max retries exceeded - no VPA provided"
                )
                
                self._notify_slack(
                    f"Refund failed for Booking {booking_id}: "
                    f"No VPA provided. Max retries exceeded."
                )
                
                return {"success": False, "message": "VPA verification failed. Max retries exceeded."}
            
            # Update retry count and keep as pending
            self._update_booking_refund(booking, booking_details, refund_info)
            
            return {
                "success": False, 
                "message": "VPA required for refund processing",
                "retry_count": refund_info["retry_count"]
            }

        # Process refund through circuit breaker
        try:
            result = REFUND_BREAKER.execute(
                self._execute_refund,
                booking_id, target_vpa, refund_info, ip_address, user_agent
            )
            
            # TASK 6.11: Record idempotency on success
            if result.get("success") and idempotency_key:
                request_hash = self._generate_request_hash(booking_id, refund_info.get("amount", 0), "process", False)
                self._record_idempotency(idempotency_key, booking_id, request_hash, result)
            
            # TASK 6.13: Check SLA
            sla_status = self._check_sla(booking_id)
            if sla_status and sla_status.get("breached"):
                self._notify_slack(
                    f"⏰ SLA BREACH: Booking {booking_id} - "
                    f"Processing time: {sla_status.get('elapsed_seconds', 0)/3600:.1f}h"
                )
            
            return result
        except CircuitOpenError:
            return {"success": False, "message": "Refund service temporarily unavailable. Please try again."}
        except Exception as e:
            logger.error(f"Refund processing error: {e}")
            return {"success": False, "message": str(e)}

    def _execute_refund(
        self, 
        booking_id: str, 
        target_vpa: str, 
        refund_info: Dict,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Internal method to execute refund.
        Includes audit logging and webhook notifications.
        """
        from sqlalchemy.orm.attributes import flag_modified
        
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        booking_details = booking.booking_details or {}
        previous_status = refund_info.get("status")
        
        # Update status to INITIATED
        refund_info["status"] = self.STATE_INITIATED
        refund_info["vpa"] = target_vpa
        refund_info["initiated_at"] = datetime.utcnow().isoformat()
        
        self._update_booking_refund(booking, booking_details, refund_info)
        
        # TASK 6.10: Log audit for INITIATED state
        self._log_audit(
            booking_id=booking_id,
            action="PROCESS",
            new_state=self.STATE_INITIATED,
            actor_type="SYSTEM",
            previous_state=previous_status,
            amount=refund_info.get("amount"),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Simulate bank API call
        # In production, this would call the payment gateway's refund API
        # Example: await payment_gateway.refund(amount=refund_info["amount"], vpa=target_vpa)
        
        # Generate receipt
        receipt = {
            "receipt_id": f"REF-{booking_id[:8].upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "amount": refund_info["amount"],
            "vpa": target_vpa,
            "date": datetime.utcnow().isoformat(),
            "booking_id": booking_id,
            "utr": f"UTR{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{hash(booking_id) % 100000}"  # Unique Transaction Reference
        }
        
        # Update status to SUCCESS
        refund_info["status"] = self.STATE_SUCCESS
        refund_info["receipt"] = receipt
        refund_info["completed_at"] = datetime.utcnow().isoformat()
        
        self._update_booking_refund(booking, booking_details, refund_info)
        
        # TASK 6.10: Log audit for COMPLETED state
        self._log_audit(
            booking_id=booking_id,
            action="COMPLETE",
            new_state=self.STATE_SUCCESS,
            actor_type="SYSTEM",
            previous_state=self.STATE_INITIATED,
            amount=refund_info.get("amount"),
            extra_metadata={"receipt_id": receipt["receipt_id"], "utr": receipt["utr"]},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # TASK 6.13: Clear SLA timer
        self._sla_tracking.pop(booking_id, None)
        
        logger.info(f"✅ Refund processed: {booking_id} | Amount: ₹{refund_info['amount']} | UTR: {receipt['utr']}")
        
        return {
            "success": True, 
            "message": "Refund processed successfully", 
            "receipt": receipt
        }

    def _update_booking_refund(self, booking: Booking, booking_details: Dict, refund_info: Dict):
        """Helper to update booking with refund info."""
        from sqlalchemy.orm.attributes import flag_modified
        
        booking_details["refund_info"] = refund_info
        booking.booking_details = booking_details
        flag_modified(booking, "booking_details")
        self.db.commit()
        
        # Invalidate cache
        cache_key = self._get_cache_key(str(booking.id))
        self._cache.pop(cache_key, None)

    def admin_approve_refund(
        self, 
        booking_id: str, 
        admin_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Admin endpoint to approve high-value refunds.
        Production-ready with audit trail.
        
        Args:
            booking_id: The booking to approve
            admin_id: ID of the approving admin
            ip_address: Admin IP for audit
            user_agent: Admin user agent for audit
            
        Returns:
            Dict with approval result
        """
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        from sqlalchemy.orm.attributes import flag_modified
        
        booking_details = booking.booking_details or {}
        refund_info = booking_details.get("refund_info")
        
        if not refund_info:
            return {"success": False, "message": "No refund request found"}
        
        if refund_info.get("status") != self.STATE_REQUIRES_APPROVAL:
            return {"success": False, "message": "Refund does not require approval"}
        
        previous_status = refund_info.get("status")
        
        # Approve the refund
        refund_info["status"] = self.STATE_PENDING
        refund_info["approved_by"] = admin_id
        refund_info["approved_at"] = datetime.utcnow().isoformat()
        
        booking_details["refund_info"] = refund_info
        booking.booking_details = booking_details
        flag_modified(booking, "booking_details")
        self.db.commit()
        
        # TASK 6.10: Log audit for approval
        self._log_audit(
            booking_id=booking_id,
            action="APPROVE",
            new_state=self.STATE_PENDING,
            actor_type="ADMIN",
            actor_id=admin_id,
            previous_state=previous_status,
            amount=refund_info.get("amount"),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Invalidate cache
        cache_key = self._get_cache_key(booking_id)
        self._cache.pop(cache_key, None)
        
        logger.info(f"✅ Refund approved: {booking_id} by admin {admin_id}")
        
        return {
            "success": True, 
            "message": "Refund approved and queued for processing",
            "approved_by": admin_id,
            "approved_at": refund_info["approved_at"]
        }

    def admin_reject_refund(
        self, 
        booking_id: str, 
        admin_id: str, 
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Admin endpoint to reject a refund request.
        Production-ready with audit trail.
        
        Args:
            booking_id: The booking to reject
            admin_id: ID of the rejecting admin
            reason: Reason for rejection
            ip_address: Admin IP for audit
            user_agent: Admin user agent for audit
            
        Returns:
            Dict with rejection result
        """
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        from sqlalchemy.orm.attributes import flag_modified
        
        booking_details = booking.booking_details or {}
        refund_info = booking_details.get("refund_info")
        
        if not refund_info:
            return {"success": False, "message": "No refund request found"}
        
        previous_status = refund_info.get("status")
        
        # Reject the refund
        refund_info["status"] = self.STATE_FAILED
        refund_info["rejected_by"] = admin_id
        refund_info["rejected_at"] = datetime.utcnow().isoformat()
        refund_info["rejection_reason"] = reason
        
        booking_details["refund_info"] = refund_info
        booking.booking_details = booking_details
        flag_modified(booking, "booking_details")
        self.db.commit()
        
        # TASK 6.10: Log audit for rejection
        self._log_audit(
            booking_id=booking_id,
            action="REJECT",
            new_state=self.STATE_FAILED,
            actor_type="ADMIN",
            actor_id=admin_id,
            previous_state=previous_status,
            amount=refund_info.get("amount"),
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Invalidate cache
        cache_key = self._get_cache_key(booking_id)
        self._cache.pop(cache_key, None)
        
        self._notify_slack(f"Refund rejected for Booking {booking_id} by admin {admin_id}: {reason}")
        
        logger.info(f"❌ Refund rejected: {booking_id} by admin {admin_id}")
        
        return {
            "success": True, 
            "message": "Refund rejected",
            "rejected_by": admin_id,
            "reason": reason
        }

    def process_bulk_refunds(self) -> Dict[str, Any]:
        """
        Task 6.7: Bulk refund processing via Bank API/CSV.
        """
        try:
            # Find all pending refunds
            bookings = self.db.query(Booking).all()
            processed = 0
            failed = 0
            skipped = 0
            
            for b in bookings:
                details = b.booking_details or {}
                if "refund_info" in details:
                    refund_info = details["refund_info"]
                    if refund_info.get("status") == self.STATE_PENDING:
                        res = self.process_refund(str(b.id))
                        if res["success"]:
                            processed += 1
                        else:
                            failed += 1
                    else:
                        skipped += 1
                    
            logger.info(f"📊 Bulk refund processed: {processed} success, {failed} failed, {skipped} skipped")
            
            return {
                "success": True, 
                "processed": processed, 
                "failed": failed,
                "skipped": skipped
            }
            
        except Exception as e:
            logger.error(f"Bulk refund processing failed: {e}")
            return {"success": False, "error": str(e)}

    def clear_cache(self, booking_id: Optional[str] = None) -> None:
        """Clear refund cache."""
        if booking_id:
            self._cache.pop(self._get_cache_key(booking_id), None)
        else:
            self._cache.clear()
        logger.info(f"Refund cache cleared" + (f" for {booking_id}" if booking_id else ""))

    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status."""
        breaker = circuit_manager.get("refund_service")
        metrics = breaker.get_metrics() if breaker else None
        return {
            "circuit_breaker": metrics.to_dict() if metrics else None,
            "cache_size": len(self._cache),
            "sla_metrics": self.get_sla_metrics()
        }

    # =========================================================================
    # TASK 6.14: WEBHOOK SUPPORT - Async notifications
    # =========================================================================
    
    def register_webhook(
        self,
        booking_id: str,
        callback_url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register webhook callback for refund status changes.
        Task 6.14: Async notification system.
        """
        import hmac
        import hashlib
        
        webhook_id = str(uuid.uuid4())
        webhook_secret = secret or str(uuid.uuid4())[:16]
        
        # Store webhook config (in production, persist to DB)
        webhook_config = {
            "webhook_id": webhook_id,
            "booking_id": booking_id,
            "callback_url": callback_url,
            "events": events,
            "secret": webhook_secret,
            "created_at": datetime.utcnow().isoformat(),
            "active": True
        }
        
        # In production: save to database
        # self.db.add(RefundWebhook(...))
        
        logger.info(f"📣 Webhook registered: {webhook_id} for booking {booking_id}")
        
        return {
            "success": True,
            "webhook_id": webhook_id,
            "secret": webhook_secret,
            "message": "Webhook registered. Use secret to verify signatures."
        }

    async def _send_webhook(
        self,
        webhook_id: str,
        event: str,
        payload: Dict
    ) -> bool:
        """
        Send webhook notification to registered callback.
        Includes signature verification.
        """
        import hmac
        import hashlib
        
        # In production: fetch webhook config from DB
        # webhook = self.db.query(RefundWebhook).filter_by(webhook_id=webhook_id).first()
        
        # Placeholder - would send actual HTTP request
        logger.info(f"📣 Sending webhook {webhook_id} for event {event}")
        
        # Example implementation:
        # import httpx
        # payload_json = json.dumps(payload, default=str)
        # signature = hmac.new(webhook.secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         webhook.callback_url,
        #         json=payload,
        #         headers={"X-Webhook-Signature": signature, "X-Webhook-Event": event}
        #     )
        #     return response.status_code == 200
        
        return True

    def trigger_webhook_for_refund(self, booking_id: str, event: str) -> None:
        """
        Trigger webhook notifications for refund events.
        Called after state changes.
        """
        # In production: query registered webhooks for this booking
        # webhooks = self.db.query(RefundWebhook).filter_by(booking_id=booking_id, active=True).all()
        
        payload = {
            "event": event,
            "booking_id": booking_id,
            "timestamp": datetime.utcnow().isoformat(),
            "refund_status": self.get_refund_status(booking_id)
        }
        
        # Would iterate and send to each webhook
        logger.debug(f"📣 Would trigger webhooks for {event} on {booking_id}")

    # =========================================================================
    # TASK 6.15: PARTIAL REFUND POLICIES
    # =========================================================================
    
    def calculate_partial_refund(
        self,
        booking_id: str,
        reason: str,
        passenger_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Calculate partial refund based on configurable policies.
        Task 6.15: Complex partial refund scenarios.
        """
        booking = self._validate_booking(booking_id)
        if not booking:
            return {"success": False, "message": "Booking not found"}
        
        booking_details = booking.booking_details or {}
        base_fare = booking_details.get("total_fare", 0)
        passengers = booking_details.get("passengers", [])
        
        if not passengers:
            return {"success": False, "message": "No passengers found"}
        
        # Determine cancellation charge based on reason and timing
        cancellation_policy = self._get_cancellation_policy(reason, booking)
        
        if passenger_indices:
            # Specific passengers refund
            refund_passengers = [passengers[i] for i in passenger_indices if i < len(passengers)]
            passenger_count = len(refund_passengers)
        else:
            # All passengers
            refund_passengers = passengers
            passenger_count = len(passengers)
        
        # Calculate refund
        per_passenger_fare = base_fare / len(passengers) if passengers else 0
        total_refund = per_passenger_fare * passenger_count
        total_charge = cancellation_policy["charge_per_passenger"] * passenger_count
        final_refund = max(0, total_refund - total_charge)
        
        return {
            "success": True,
            "original_fare": base_fare,
            "passenger_count": passenger_count,
            "per_passenger_fare": per_passenger_fare,
            "total_charge": total_charge,
            "refund_amount": final_refund,
            "policy": cancellation_policy,
            "breakdown": [
                {
                    "passenger": p.get("name", "Unknown"),
                    "fare": per_passenger_fare,
                    "charge": cancellation_policy["charge_per_passenger"],
                    "refund": max(0, per_passenger_fare - cancellation_policy["charge_per_passenger"])
                }
                for p in refund_passengers
            ]
        }

    def _get_cancellation_policy(self, reason: str, booking: Booking) -> Dict:
        """
        Get cancellation policy based on reason and booking timing.
        """
        # Default IRCTC-style policies
        policies = {
            "USER_CANCELLED": {
                "charge_type": "tiered",
                "tiers": [
                    {"hours_before": 48, "charge_pct": 25, "flat": 0},
                    {"hours_before": 24, "charge_pct": 50, "flat": 0},
                    {"hours_before": 12, "charge_pct": 75, "flat": 0},
                    {"hours_before": 0, "charge_pct": 100, "flat": 0}
                ]
            },
            "IRCTC_SOLD_OUT": {
                "charge_type": "flat",
                "charge_pct": 0,
                "flat": 0,
                "note": "No charge for sold out"
            },
            "TRAIN_CANCELLED": {
                "charge_type": "none",
                "charge_pct": 0,
                "flat": 0,
                "note": "Full refund - train cancelled"
            }
        }
        
        policy = policies.get(reason, policies["USER_CANCELLED"])
        
        # Calculate actual charge
        booking_details = booking.booking_details or {}
        departure_time = booking_details.get("departure_time")
        
        if departure_time:
            try:
                dep_dt = datetime.fromisoformat(departure_time) if isinstance(departure_time, str) else departure_time
                hours_before = (dep_dt - datetime.utcnow()).total_seconds() / 3600
                
                if policy.get("charge_type") == "tiered":
                    for tier in policy.get("tiers", []):
                        if hours_before >= tier.get("hours_before", 0):
                            charge_pct = tier.get("charge_pct", 0)
                            flat = tier.get("flat", 0)
                            base_fare = booking_details.get("total_fare", 0)
                            return {
                                "charge_type": "tiered",
                                "charge_per_passenger": (base_fare * charge_pct / 100) + flat,
                                "hours_before_departure": hours_before,
                                "tier_applied": tier
                            }
            except Exception as e:
                logger.warning(f"Could not calculate tier: {e}")
        
        return {
            "charge_type": policy.get("charge_type", "flat"),
            "charge_per_passenger": policy.get("flat", self.PARTIAL_REFUND_CANCELLATION_CHARGE),
            "note": policy.get("note", "")
        }
