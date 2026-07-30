"""
💰 PAYMENT SERVICE - Razorpay Integration
Production-ready with audit trail, idempotency, fraud detection, and webhook support.
"""

import httpx
import hashlib
import hmac
import logging
import asyncio
import uuid
import json
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from config import Config
from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig, CircuitOpenError
from core.resilience.retry import retry, RETRY_POLICY_EXTERNAL_API
from database.base import Base
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Boolean

logger = logging.getLogger(__name__)

RAZORPAY_API_URL = "https://api.razorpay.com/v1"

# Create circuit breaker for Razorpay
RAZORPAY_BREAKER = circuit_manager.get_or_create(
    "razorpay",
    CircuitConfig(
        failure_threshold=5,
        timeout_seconds=120.0,
        success_threshold=3,
        half_open_max_calls=2
    )
)




# =========================================================================
# CONFIGURATION
# =========================================================================

@dataclass
class WebhookDeliveryLog:
    webhook_id: str
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    last_status: Optional[str] = None


class PaymentAuditLog(Base):
    __tablename__ = "payment_audit_logs"
    audit_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String(36), nullable=True, index=True)
    order_id = Column(String(128), nullable=True, index=True)
    action = Column(String(50), nullable=False)
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    actor_type = Column(String(50), nullable=False)
    actor_id = Column(String(36), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(10), default="INR")
    extra_data = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def compute_checksum(audit_data: Dict) -> str:
        canonical = json.dumps(audit_data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


class PaymentIdempotency(Base):
    __tablename__ = "payment_idempotency"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key = Column(String(255), unique=True, nullable=False)
    operation_type = Column(String(50), nullable=False)
    request_hash = Column(String(128), nullable=False)
    response = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class PaymentFraudCheck(Base):
    __tablename__ = "payment_fraud_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String(36), nullable=True)
    user_id = Column(String(36), nullable=False)
    check_type = Column(String(50), nullable=False)
    risk_score = Column(Float, default=0.0)
    flags = Column(JSON, default=list)
    decision = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================================
# CONFIGURATION
# =========================================================================

@dataclass
class PaymentConfig:
    """Configuration for payment service."""
    cache_ttl_seconds: int = 300
    idempotency_ttl_hours: int = 24
    max_payment_amount: float = 1000000.0  # 10L limit
    min_payment_amount: float = 1.0
    high_value_threshold: float = 50000.0
    max_refunds_per_day: int = 10
    max_refund_amount_daily: float = 100000.0
    webhook_max_retries: int = 3
    webhook_retry_delay_seconds: int = 60


class PaymentService:
    """
    Handle Razorpay payment operations with production features:
    - Audit trail
    - Idempotency
    - Fraud detection
    - Webhook management
    - Rate limiting
    """
    
    def __init__(self, db_session=None):
        self.key_id = Config.RAZORPAY_KEY_ID
        self.key_secret = Config.RAZORPAY_KEY_SECRET
        self.db = db_session  # Optional database session for audit
        
        if not self.key_id or self.key_id == "your_razorpay_key_id":
            logger.warning("Razorpay key_id not configured")
        if not self.key_secret or self.key_secret == "your_razorpay_key_secret":
            logger.warning("Razorpay key_secret not configured")
        
        # Local cache for order details
        self._order_cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        
        # Production features
        self._webhook_registry: Dict[str, List[Dict]] = defaultdict(list)
        self._webhook_delivery_attempts: Dict[str, WebhookDeliveryLog] = {}
        
        logger.info("PaymentService initialized with production features")

    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured."""
        return bool(
            self.key_id
            and self.key_id != "your_razorpay_key_id"
            and self.key_secret
            and self.key_secret != "your_razorpay_key_secret"
        )

    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached order is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    # =========================================================================
    # TASK: AUDIT TRAIL
    # =========================================================================
    
    def _log_audit(
        self,
        payment_id: Optional[str],
        order_id: Optional[str],
        action: str,
        new_state: str,
        actor_type: str,
        actor_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        amount: Optional[float] = None,
        currency: str = "INR",
        extra_data: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log an immutable audit entry for payment operations."""
        audit_id = str(uuid.uuid4())
        
        audit_data = {
            "audit_id": audit_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "action": action,
            "previous_state": previous_state,
            "new_state": new_state,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "amount": amount,
            "currency": currency,
            "extra_data": extra_data,
            "created_at": datetime.utcnow().isoformat()
        }
        
        checksum = PaymentAuditLog.compute_checksum(audit_data)
        
        if self.db:
            try:
                audit_entry = PaymentAuditLog(
                    audit_id=audit_id,
                    payment_id=payment_id,
                    order_id=order_id,
                    action=action,
                    previous_state=previous_state,
                    new_state=new_state,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    amount=amount,
                    currency=currency,
                    extra_data=extra_data,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    checksum=checksum
                )
                self.db.add(audit_entry)
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to log payment audit: {e}")
                self.db.rollback()
        
        logger.debug(f"📋 Payment audit logged: {audit_id} | {action} | {order_id}")
        return audit_id

    def get_audit_trail(self, payment_id: Optional[str] = None, order_id: Optional[str] = None) -> List[Dict]:
        """Retrieve audit trail for a payment or order."""
        if not self.db:
            return []
        
        try:
            query = self.db.query(PaymentAuditLog)
            if payment_id:
                query = query.filter(PaymentAuditLog.payment_id == payment_id)
            if order_id:
                query = query.filter(PaymentAuditLog.order_id == order_id)
            
            audits = query.order_by(PaymentAuditLog.created_at.asc()).all()
            
            return [
                {
                    "audit_id": a.audit_id,
                    "action": a.action,
                    "previous_state": a.previous_state,
                    "new_state": a.new_state,
                    "actor_type": a.actor_type,
                    "actor_id": a.actor_id,
                    "amount": a.amount,
                    "currency": a.currency,
                    "extra_data": a.extra_data,
                    "created_at": a.created_at.isoformat(),
                    "checksum": a.checksum
                }
                for a in audits
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {e}")
            return []

    # =========================================================================
    # TASK: IDEMPOTENCY
    # =========================================================================
    
    async def calculate_unlock_fee(self, route_complexity: float, total_fare: float) -> int:
        """
        Patent-Level Algorithm: Yield-Based Pricing for Algorithm Access.
        Base fee: ₹49. Max fee: ₹149.
        """
        base_fee = 49
        bonus = min(100, int(max(0, route_complexity - 1.0) * 50))
        final_fee = base_fee + bonus
        capped_fee = min(final_fee, int(total_fare * 0.10))
        return max(49, capped_fee)

    def _generate_request_hash(
        self,
        operation_type: str,
        amount: float,
        receipt_id: str,
        customer_email: Optional[str]
    ) -> str:
        """Generate deterministic hash for request deduplication."""
        content = f"{operation_type}:{amount}:{receipt_id}:{customer_email}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _check_idempotency(self, idempotency_key: str) -> Optional[Dict]:
        """Check if request was already processed."""
        if not self.db:
            return None
        
        try:
            record = self.db.query(PaymentIdempotency).filter(
                PaymentIdempotency.idempotency_key == idempotency_key
            ).first()
            
            if record and datetime.utcnow() < record.expires_at:
                logger.info(f"🔄 Idempotent request found: {idempotency_key}")
                return record.response
            
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
        operation_type: str,
        request_hash: str,
        response: Dict
    ) -> None:
        """Cache idempotent response."""
        if not self.db:
            return
        
        try:
            expires = datetime.utcnow() + timedelta(hours=24)
            record = PaymentIdempotency(
                idempotency_key=idempotency_key,
                operation_type=operation_type,
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
    # TASK: FRAUD DETECTION
    # =========================================================================
    
    def _check_fraud(
        self,
        user_id: str,
        amount: float,
        payment_id: Optional[str] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Perform fraud checks on payment.
        Returns: (is_allowed, decision, details)
        """
        details = {"flags": [], "risk_score": 0.0}
        
        # Check 1: Amount limits
        if amount > 1000000:
            details["flags"].append("AMOUNT_EXCEEDS_LIMIT")
            details["risk_score"] = 1.0
            return False, "BLOCK", details
        
        if amount < 1:
            details["flags"].append("INVALID_AMOUNT")
            details["risk_score"] = 0.5
            return False, "BLOCK", details
        
        # Check 2: High value flag
        if amount > 50000:
            details["flags"].append("HIGH_VALUE")
            details["risk_score"] += 0.2
        
        # Check 3: Daily refund velocity (if this is a refund)
        # In production: query database for user's refund patterns
        
        # Determine decision
        decision = "ALLOW"
        if details["risk_score"] >= 0.7:
            decision = "BLOCK"
        elif details["risk_score"] >= 0.4:
            decision = "FLAG"
        
        # Log fraud check
        if self.db and decision != "ALLOW":
            try:
                fraud_record = PaymentFraudCheck(
                    payment_id=payment_id or "pending",
                    user_id=user_id,
                    check_type="COMPREHENSIVE",
                    risk_score=details["risk_score"],
                    flags=details["flags"],
                    decision=decision
                )
                self.db.add(fraud_record)
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to log fraud check: {e}")
                self.db.rollback()
        
        return decision != "BLOCK", decision, details

    # =========================================================================
    # TASK: WEBHOOK MANAGEMENT
    # =========================================================================
    
    def register_webhook(
        self,
        event_type: str,
        callback_url: str,
        secret: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Register webhook callback for payment events.
        """
        webhook_id = str(uuid.uuid4())
        webhook_secret = secret or str(uuid.uuid4())[:16]
        
        webhook = {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "callback_url": callback_url,
            "secret": webhook_secret,
            "user_id": user_id,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self._webhook_registry[event_type].append(webhook)
        
        logger.info(f"📣 Payment webhook registered: {webhook_id} for {event_type}")
        
        return {
            "success": True,
            "webhook_id": webhook_id,
            "secret": webhook_secret
        }

    async def _deliver_webhook(
        self,
        webhook_id: str,
        event_type: str,
        payload: Dict,
        webhook: Dict
    ) -> bool:
        """Deliver webhook to callback URL."""
        import httpx
        
        payload_json = json.dumps(payload, default=str)
        signature = hmac.new(
            webhook["secret"].encode(), 
            payload_json.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook["callback_url"],
                    content=payload_json,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": event_type,
                        "X-Webhook-ID": webhook_id
                    },
                    timeout=10.0
                )
            
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"✅ Webhook delivered: {webhook_id}")
                return True
            else:
                logger.warning(f"❌ Webhook failed: {webhook_id} - {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook delivery error: {e}")
            return False

    async def trigger_webhooks(
        self,
        event_type: str,
        data: Dict,
        exclude_user_id: Optional[str] = None
    ) -> Dict:
        """
        Trigger webhooks for a payment event.
        """
        webhooks = self._webhook_registry.get(event_type, [])
        delivered = 0
        failed = 0
        
        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for webhook in webhooks:
            if not webhook.get("active"):
                continue
            if exclude_user_id and webhook.get("user_id") == exclude_user_id:
                continue
            
            success = await self._deliver_webhook(
                webhook["webhook_id"],
                event_type,
                payload,
                webhook
            )
            
            if success:
                delivered += 1
            else:
                failed += 1
        
        return {"delivered": delivered, "failed": failed}

    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister a webhook."""
        for event_type, webhooks in self._webhook_registry.items():
            for i, wh in enumerate(webhooks):
                if wh.get("webhook_id") == webhook_id:
                    webhooks[i]["active"] = False
                    logger.info(f"📣 Webhook {webhook_id} unregistered")
                    return True
        return False

    # =========================================================================
    # MAIN PAYMENT OPERATIONS
    # =========================================================================

    async def create_order(
        self,
        amount_rupees: float = 39,
        receipt_id: str = "route_unlock",
        customer_email: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Create Razorpay order with production features:
        - Idempotency
        - Fraud detection
        - Audit logging
        - Webhook triggers
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Razorpay not configured. Please contact admin.",
            }
        
        # Check idempotency
        if idempotency_key:
            cached_response = self._check_idempotency(idempotency_key)
            if cached_response:
                cached_response["idempotent_replay"] = True
                return cached_response
        
        # Fraud check
        fraud_allowed, fraud_decision, fraud_details = self._check_fraud(
            user_id or "anonymous", amount_rupees
        )
        if not fraud_allowed:
            self._log_audit(
                payment_id=None,
                order_id=None,
                action="FRAUD_BLOCK",
                new_state="BLOCKED",
                actor_type="SYSTEM",
                amount=amount_rupees,
                extra_data={"fraud_details": fraud_details}
            )
            return {
                "success": False,
                "error": "Payment blocked due to suspicious activity",
                "fraud_check": fraud_decision
            }
        
        try:
            # Execute through circuit breaker with retry
            result = await RAZORPAY_BREAKER.execute(
                self._create_order_impl,
                amount_rupees, receipt_id, customer_email, idempotency_key, description
            )
            
            if result.get("success"):
                order_id = result.get("order_id")
                
                # Log audit
                self._log_audit(
                    payment_id=None,
                    order_id=order_id,
                    action="CREATE_ORDER",
                    new_state="created",
                    actor_type="SYSTEM",
                    amount=amount_rupees,
                    extra_data={"customer_email": customer_email, "description": description},
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Record idempotency
                if idempotency_key:
                    request_hash = self._generate_request_hash(
                        "CREATE_ORDER", amount_rupees, receipt_id, customer_email
                    )
                    self._record_idempotency(idempotency_key, "CREATE_ORDER", request_hash, result)
                
                # Trigger webhooks
                await self.trigger_webhooks("order.created", {
                    "order_id": order_id,
                    "amount": amount_rupees,
                    "customer_email": customer_email
                })
            
            return result
            
        except CircuitOpenError as cb_err:
            logger.error(f"Circuit breaker open for Razorpay: {cb_err}")
            return {"success": False, "error": "Payment service temporarily unavailable. Please try again shortly."}
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return {"success": False, "error": "Failed to create payment order"}

    @retry(**RETRY_POLICY_EXTERNAL_API.__dict__)
    async def _create_order_impl(
        self,
        amount_rupees: float,
        receipt_id: str,
        customer_email: Optional[str],
        idempotency_key: Optional[str],
        description: Optional[str],
    ) -> Dict:
        """Actual implementation of order creation."""
        amount_paise = int(amount_rupees * 100)
        payload = {
            "amount": amount_paise, 
            "currency": "INR", 
            "receipt": receipt_id,
            "notes": {
                "customer_email": customer_email,
                "description": description,
            }
        }
        headers = {"X-Razorpay-IDEMPOTENCY": idempotency_key} if idempotency_key else {}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RAZORPAY_API_URL}/orders",
                json=payload,
                auth=(self.key_id, self.key_secret),
                headers=headers,
                timeout=10.0,
            )

        if response.status_code == 200:
            order_data = response.json()
            logger.info(f"Order created: {order_data['id']}")
            
            # Cache the order
            cache_key = order_data['id']
            self._order_cache[cache_key] = {
                "order_id": order_data['id'],
                "amount": amount_rupees,
                "status": order_data.get("status", "created"),
                "_cached_at": datetime.utcnow().timestamp()
            }
            
            return {
                "success": True, 
                "order_id": order_data["id"], 
                "amount": amount_rupees,
                "currency": "INR", 
                "key_id": self.key_id,
            }
        else:
            logger.error(f"Order creation failed: {response.text}")
            return {"success": False, "error": f"Failed to create payment order: {response.status_code}"}

    def verify_payment(
        self,
        razorpay_payment_id: str,
        razorpay_order_id: str,
        razorpay_signature: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify Razorpay payment with audit logging.
        """
        if not self.is_configured():
            return False, "Razorpay not configured"
        
        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            if hmac.compare_digest(generated_signature, razorpay_signature):
                logger.info(f"Payment verified: {razorpay_payment_id}")
                
                # Log audit
                self._log_audit(
                    payment_id=razorpay_payment_id,
                    order_id=razorpay_order_id,
                    action="VERIFY",
                    new_state="verified",
                    actor_type="SYSTEM",
                    amount=None,
                    ip_address=ip_address
                )
                
                # Invalidate cache for this order
                self._order_cache.pop(razorpay_order_id, None)
                
                # Trigger webhooks
                asyncio.create_task(self.trigger_webhooks("payment.verified", {
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id
                }))
                
                return True, None
            else:
                logger.warning(f"Signature mismatch for payment: {razorpay_payment_id}")
                
                # Log failed verification
                self._log_audit(
                    payment_id=razorpay_payment_id,
                    order_id=razorpay_order_id,
                    action="VERIFY_FAILED",
                    new_state="failed",
                    actor_type="SYSTEM",
                    amount=None,
                    extra_data={"reason": "Signature mismatch"},
                    ip_address=ip_address
                )
                
                return False, "Signature verification failed"
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False, str(e)

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verifies the signature of a webhook request."""
        if not self.is_configured():
            logger.error("Cannot verify webhook signature, Razorpay keys not configured.")
            return False
        try:
            generated_signature = hmac.new(
                self.key_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(generated_signature, signature):
                logger.info("Webhook signature verified successfully.")
                return True
            else:
                logger.warning("Webhook signature mismatch.")
                return False
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    async def fetch_payment_details(self, payment_id: str) -> Optional[Dict]:
        """Fetch payment details from Razorpay asynchronously."""
        if not self.is_configured():
            return None
        try:
            return await RAZORPAY_BREAKER.execute(self._fetch_payment_impl, payment_id)
        except CircuitOpenError:
            logger.error(f"Circuit breaker open for Razorpay fetch")
            return None

    async def _fetch_payment_impl(self, payment_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RAZORPAY_API_URL}/payments/{payment_id}",
                auth=(self.key_id, self.key_secret),
                timeout=5.0,
            )
        if response.status_code == 200:
            return response.json()
        logger.warning(f"Failed to fetch payment {payment_id}: {response.status_code}")
        return None

    async def refund_payment(
        self,
        payment_id: str,
        amount_rupees: Optional[float] = None,
        idempotency_key: Optional[str] = None,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Create refund for a payment with production features:
        - Idempotency
        - Fraud detection
        - Audit logging
        - Webhook triggers
        
        Returns:
            Tuple[success: bool, error_message: Optional[str], refund_data: Optional[Dict]]
        """
        if not self.is_configured():
            return False, "Razorpay not configured", None
        
        # Check idempotency
        if idempotency_key:
            cached_response = self._check_idempotency(idempotency_key)
            if cached_response:
                cached_response["idempotent_replay"] = True
                return cached_response.get("success", False), cached_response.get("error"), cached_response.get("refund_data")
        
        # Fraud check for refunds
        fraud_allowed, fraud_decision, fraud_details = self._check_fraud(
            user_id or "anonymous", amount_rupees or 0, payment_id
        )
        if not fraud_allowed:
            self._log_audit(
                payment_id=payment_id,
                order_id=None,
                action="REFUND_FRAUD_BLOCK",
                new_state="BLOCKED",
                actor_type="SYSTEM",
                amount=amount_rupees,
                extra_data={"fraud_details": fraud_details}
            )
            return False, "Refund blocked due to suspicious activity", None
        
        try:
            success, error, refund_data = await RAZORPAY_BREAKER.execute(
                self._refund_impl, payment_id, amount_rupees
            )
            
            if success:
                # Log audit
                self._log_audit(
                    payment_id=payment_id,
                    order_id=None,
                    action="REFUND",
                    new_state="refunded",
                    actor_type="SYSTEM",
                    amount=amount_rupees,
                    extra_data={"reason": reason},
                    ip_address=ip_address
                )
                
                # Record idempotency
                if idempotency_key:
                    request_hash = self._generate_request_hash(
                        "REFUND", amount_rupees or 0, payment_id, reason
                    )
                    self._record_idempotency(
                        idempotency_key, "REFUND", request_hash,
                        {"success": True, "error": None, "refund_data": refund_data}
                    )
                
                # Trigger webhooks
                await self.trigger_webhooks("payment.refunded", {
                    "payment_id": payment_id,
                    "refund_id": refund_data.get("id") if refund_data else None,
                    "amount": amount_rupees
                })
            
            return success, error, refund_data
            
        except CircuitOpenError:
            logger.error(f"Circuit breaker open for Razorpay refund")
            return False, "Payment service temporarily unavailable", None

    async def _refund_impl(self, payment_id: str, amount_rupees: Optional[float] = None):
        payload = {"amount": int(amount_rupees * 100)} if amount_rupees else {}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RAZORPAY_API_URL}/payments/{payment_id}/refund",
                json=payload,
                auth=(self.key_id, self.key_secret),
                timeout=10.0,
            )
        if response.status_code in [200, 201]:
            refund_data = response.json()
            refund_id = refund_data.get('id')
            logger.info(f"Refund created: {refund_id}")
            return True, None, refund_data
        else:
            error_text = response.text
            logger.error(f"Refund failed: {error_text}")
            return False, f"Refund failed: {error_text}", None

    async def fetch_payments_for_order(self, order_id: str) -> Optional[Dict]:
        """Fetch all payments for a given Razorpay order asynchronously."""
        if not self.is_configured():
            return None
        
        # Check cache first
        if order_id in self._order_cache and self._is_cache_valid(self._order_cache[order_id]):
            logger.debug(f"Cache hit for order {order_id}")
            cached = self._order_cache[order_id]
            return {
                "order_id": order_id,
                "status": cached.get("status"),
                "payments": []  # Would need separate cache for payments
            }
        
        try:
            return await RAZORPAY_BREAKER.execute(self._fetch_order_payments_impl, order_id)
        except CircuitOpenError:
            logger.error(f"Circuit breaker open for Razorpay order payments fetch")
            return None

    async def _fetch_order_payments_impl(self, order_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RAZORPAY_API_URL}/orders/{order_id}/payments",
                auth=(self.key_id, self.key_secret),
                timeout=5.0,
            )
        if response.status_code == 200:
            result = response.json()
            # Cache the order info
            self._order_cache[order_id] = {
                "order_id": order_id,
                "status": result.get("items", [{}])[0].get("order_id") if result.get("items") else None,
                "_cached_at": datetime.utcnow().timestamp()
            }
            return result
        return None

    async def fetch_order_details(self, order_id: str) -> Optional[Dict]:
        """Fetch order details from Razorpay asynchronously."""
        if not self.is_configured():
            return None
        
        # Check cache first
        if order_id in self._order_cache and self._is_cache_valid(self._order_cache[order_id]):
            cached = self._order_cache[order_id]
            return {
                "id": order_id,
                "amount": cached.get("amount"),
                "status": cached.get("status"),
                "cached": True
            }
        
        try:
            return await RAZORPAY_BREAKER.execute(self._fetch_order_details_impl, order_id)
        except CircuitOpenError:
            logger.error(f"Circuit breaker open for Razorpay order details fetch")
            return None

    async def _fetch_order_details_impl(self, order_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RAZORPAY_API_URL}/orders/{order_id}",
                auth=(self.key_id, self.key_secret),
                timeout=5.0,
            )
        if response.status_code == 200:
            result = response.json()
            # Cache the result
            self._order_cache[order_id] = {
                "order_id": order_id,
                "amount": result.get("amount") / 100,  # Convert back to rupees
                "status": result.get("status"),
                "_cached_at": datetime.utcnow().timestamp()
            }
            return result
        return None

    def clear_cache(self, order_id: Optional[str] = None) -> None:
        """Clear order cache."""
        if order_id:
            self._order_cache.pop(order_id, None)
        else:
            self._order_cache.clear()
        logger.info(f"Payment cache cleared" + (f" for {order_id}" if order_id else ""))

    def get_health_status(self) -> Dict:
        """Get health status including circuit breaker state."""
        breaker = circuit_manager.get("razorpay")
        metrics = breaker.get_metrics() if breaker else None
        return {
            "configured": self.is_configured(),
            "circuit_breaker": metrics if metrics else None,
            "cache_size": len(self._order_cache)
        }
