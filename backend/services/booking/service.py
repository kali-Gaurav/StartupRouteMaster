"""
🎫 BOOKING SERVICE - Booking Management
Production-ready with audit trail, idempotency, fraud detection, and webhook support.
"""

import asyncio
import logging
import secrets
import hashlib
import uuid
import json
import threading
from time import sleep
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any, Tuple, cast, TYPE_CHECKING
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from collections import defaultdict, deque

if TYPE_CHECKING:
    from database.models import Booking
from database.models import Booking, BookingFraudCheck, BookingIdempotency, Payment, User, PassengerDetails, BookingAuditLog
from core.data_utils.structures import EscrowStatus
from core.engines.booking_state import BookingStateMachine
BookingModel = cast(Any, Booking)
from schemas import BookingResponseSchema
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import joinedload, Session
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Boolean
from database.base import Base # Import Base directly from database.base
from services.orchestration.event_producer import publish_booking_created
from services.communication.notifications import notification_service
from database.infrastructure.config import Config
from utils.generators import generate_pnr
from utils.validation import validate_date_string
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig, CircuitOpenError
from core.resilience.retry import RetryPolicy, RETRY_POLICY_DATABASE, RETRY_POLICY_EXTERNAL_API

logger = logging.getLogger(__name__)


def _schedule_background_task(coro, label: str) -> None:
    """Run async side effects from sync service methods without breaking the main transaction."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        def _runner():
            try:
                asyncio.run(coro)
            except Exception as exc:
                logger.debug("Background task failed: %s: %s", label, exc)

        threading.Thread(target=_runner, name=f"booking-bg-{label}", daemon=True).start()
    except Exception as exc:
        logger.debug("Background task scheduling failed: %s: %s", label, exc)


# =========================================================================
# PRODUCTION MODELS
# =========================================================================

# BookingAuditLog definition is now in database/models.py

# =========================================================================
# CONFIGURATION
# =========================================================================

@dataclass
class BookingConfig:
    """Configuration for booking service."""
    max_bookings_per_user_24h: int = 5
    max_bookings_per_user_7d: int = 20
    max_amount_per_booking: float = 100000.0
    high_value_threshold: float = 50000.0
    lock_timeout_seconds: int = 30
    max_retries: int = 3
    idempotency_ttl_hours: int = 24


class DistributedLock:
    """Redis-based distributed lock for booking operations."""
    
    def __init__(self, redis_client, lock_prefix: str = "booking:lock:"):
        self.redis = redis_client
        self.lock_prefix = lock_prefix
        self._local_locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock_key(self, lock_id: str) -> str:
        return f"{self.lock_prefix}{lock_id}"
    
    async def acquire(self, lock_id: str, timeout_seconds: int = 30) -> Optional[str]:
        """
        Acquire a distributed lock.
        
        Args:
            lock_id: Unique identifier for the lock
            timeout_seconds: Lock expiration time
            
        Returns:
            Lock token if acquired, None otherwise
        """
        if not self.redis:
            # Fallback to local lock if Redis unavailable
            if lock_id not in self._local_locks:
                self._local_locks[lock_id] = asyncio.Lock()
            await self._local_locks[lock_id].acquire()
            return f"local:{lock_id}"
        
        lock_key = self._get_lock_key(lock_id)
        token = secrets.token_hex(8)
        
        # Try to set the lock with NX (only if not exists) and EX (expiration)
        acquired = await self.redis.set(
            lock_key, 
            token, 
            nx=True, 
            ex=timeout_seconds
        )
        
        if acquired:
            logger.debug(f"🔒 Acquired lock: {lock_id}")
            return token
        return None
    
    async def release(self, lock_id: str, token: str) -> bool:
        """
        Release a distributed lock.
        
        Args:
            lock_id: Lock identifier
            token: Lock token received from acquire()
            
        Returns:
            True if released, False otherwise
        """
        # Handle local lock fallback
        if token.startswith("local:"):
            real_lock_id = token.split(":", 1)[1]
            if real_lock_id in self._local_locks:
                self._local_locks[real_lock_id].release()
            return True
        
        if not self.redis:
            return False
            
        lock_key = self._get_lock_key(lock_id)
        
        # Use Lua script for atomic check-and-delete
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(release_script, 1, lock_key, token)
        logger.debug(f"🔓 Released lock: {lock_id} = {bool(result)}")
        return bool(result)
    
    @asynccontextmanager
    async def lock(self, lock_id: str, timeout_seconds: int = 30):
        """
        Context manager for acquiring and releasing a lock.
        
        Usage:
            async with lock_manager.lock("booking:user123:date"):
                # Critical section
                pass
        """
        token = await self.acquire(lock_id, timeout_seconds)
        if not token:
            raise LockAcquisitionError(f"Failed to acquire lock: {lock_id}")
        
        try:
            yield token
        finally:
            await self.release(lock_id, token)


class LockAcquisitionError(Exception):
    """Raised when a distributed lock cannot be acquired."""
    pass


class BookingServiceMetrics:
    """Metrics tracking for booking service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

    async def record_booking(self, action: str, success: bool, duration_ms: float):
        """Record booking metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "action": action,
                "success": success,
                "duration_ms": duration_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}

        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_action = {}
        for m in self._metrics:
            action = m["action"]
            if action not in by_action:
                by_action[action] = {"total": 0, "success": 0}
            by_action[action]["total"] += 1
            if m["success"]:
                by_action[action]["success"] += 1

        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_action": by_action
        }


class BookingService:
    """
    Handle booking creation and management with production features:
    - Distributed locking
    - Idempotency
    - Audit trail
    - Fraud detection
    - Webhook support
    """

    MAX_RETRIES = 3
    LOCK_TIMEOUT_SECONDS = 30

    def __init__(self, db: Optional[Session] = None):
        self.db: Session = cast(Session, db)
        self._lock_manager: Optional[DistributedLock] = None
        self._redis_client = None

        # Circuit breakers for external services
        self._redis_breaker = circuit_breaker_manager.get_or_create(
            "booking_redis",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "booking_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=60.0, success_threshold=3)
        )
        self._kafka_breaker = circuit_breaker_manager.get_or_create(
            "booking_kafka",
            CircuitConfig(failure_threshold=3, timeout_seconds=30.0, success_threshold=2)
        )

        # Retry policies
        self._redis_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        self._db_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, DBAPIError)
            ]
        )

        # Metrics tracking
        self._metrics = BookingServiceMetrics()

        # Production config
        self.booking_config = BookingConfig()
        self._webhook_registry: Dict[str, List[Dict]] = defaultdict(list)

        logger.info("BookingService initialized with production features and resilience patterns")

    def _get_redis(self):
        """Lazy initialization of Redis client."""
        if self._redis_client is None:
            try:
                from core.infrastructure.redis_manager import redis_client as redis
                self._redis_client = redis
            except Exception:
                pass
        return self._redis_client

    def _get_lock_manager(self) -> DistributedLock:
        """Get or create the distributed lock manager."""
        if self._lock_manager is None:
            redis = self._get_redis()
            self._lock_manager = DistributedLock(redis)
        return self._lock_manager

    def _generate_idempotency_key(self, user_id: str, travel_date: str, route_id: str) -> str:
        """Generate a unique idempotency key for a booking request."""
        key_data = f"{user_id}:{travel_date}:{route_id}"
        return f"booking:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

    async def _check_idempotency(self, idempotency_key: str) -> Optional[Booking]:
        """Check if a booking with this idempotency key already exists."""
        redis = self._get_redis()
        if not redis:
            try:
                record = self.db.query(BookingIdempotency).filter(
                    BookingIdempotency.idempotency_key == idempotency_key
                ).first()
                if not record:
                    return None
                return self.db.query(Booking).filter(BookingModel.id == record.booking_id).first()
            except Exception:
                return None
        
        cached_id = await redis.get(f"idempotency:{idempotency_key}")
        if cached_id:
            try:
                return self.db.query(Booking).filter(BookingModel.id == cached_id.decode()).first()
            except Exception:
                pass
        return None

    def get_booking_by_idempotency(self, idempotency_key: str) -> Optional[Booking]:
        """Synchronous idempotency lookup for API handlers."""
        try:
            record = self.db.query(BookingIdempotency).filter(
                BookingIdempotency.idempotency_key == idempotency_key
            ).first()
            if not record:
                return None
            return self.db.query(Booking).filter(BookingModel.id == record.booking_id).first()
        except Exception as e:
            logger.error(f"Failed to fetch booking by idempotency key: {e}")
            return None

    async def _cache_idempotency(self, idempotency_key: str, booking_id: str, ttl: int = 86400) -> None:
        """Cache the idempotency check result."""
        redis = self._get_redis()
        if redis:
            await redis.set(f"idempotency:{idempotency_key}", booking_id, ex=ttl)

    def _persist_idempotency(self, idempotency_key: str, booking_id: str, request_hash: str = "") -> None:
        """Persist idempotency result in the durable user database."""
        try:
            existing = self.db.query(BookingIdempotency).filter(
                BookingIdempotency.idempotency_key == idempotency_key
            ).first()
            if existing:
                return
            record = BookingIdempotency(
                idempotency_key=idempotency_key,
                booking_id=booking_id,
                request_hash=request_hash or hashlib.sha256(idempotency_key.encode()).hexdigest(),
                expires_at=datetime.utcnow() + timedelta(hours=BookingConfig().idempotency_ttl_hours),
            )
            self.db.add(record)
            self.db.flush()
        except Exception as e:
            logger.error(f"Failed to persist booking idempotency: {e}")

    # =========================================================================
    # TASK: AUDIT TRAIL
    # =========================================================================
    
    def _log_audit(
        self,
        booking_id: Optional[str],
        pnr_number: Optional[str],
        action: str,
        new_state: str,
        actor_type: str,
        actor_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
        extra_data: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log an immutable audit entry for booking operations."""
        audit_id = str(uuid.uuid4())
        
        audit_data = {
            "audit_id": audit_id,
            "booking_id": booking_id,
            "pnr_number": pnr_number,
            "action": action,
            "previous_state": previous_state,
            "new_state": new_state,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "amount": amount,
            "reason": reason,
            "extra_data": extra_data,
            "created_at": datetime.utcnow().isoformat()
        }
        
        checksum = hashlib.sha256(json.dumps(audit_data, sort_keys=True, default=str).encode()).hexdigest()
        
        try:
            audit_entry = BookingAuditLog(
                audit_id=audit_id,
                booking_id=booking_id,
                pnr_number=pnr_number,
                action=action,
                previous_state=previous_state,
                new_state=new_state,
                actor_type=actor_type,
                actor_id=actor_id,
                amount=amount,
                reason=reason,
                extra_data=extra_data,
                ip_address=ip_address,
                user_agent=user_agent,
                checksum=checksum
            )
            self.db.add(audit_entry)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log booking audit: {e}")
            self.db.rollback()
        
        logger.debug(f"📋 Booking audit logged: {audit_id} | {action} | {pnr_number}")
        return audit_id

    def get_audit_trail(self, booking_id: Optional[str] = None, pnr_number: Optional[str] = None) -> List[Dict]:
        """Retrieve audit trail for a booking."""
        try:
            query = self.db.query(BookingAuditLog)
            if booking_id:
                query = query.filter(BookingAuditLog.booking_id == booking_id)
            if pnr_number:
                query = query.filter(BookingAuditLog.pnr_number == pnr_number)
            
            audits = query.order_by(BookingAuditLog.created_at.asc()).limit(100).all()
            
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
                    "extra_data": a.extra_data,
                    "created_at": a.created_at.isoformat(),
                    "checksum": a.checksum
                }
                for a in audits
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve booking audit: {e}")
            return []

    # =========================================================================
    # TASK: FRAUD DETECTION
    # =========================================================================
    
    def _check_fraud(
        self,
        user_id: str,
        amount: float,
        booking_id: Optional[str] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Perform fraud checks on booking.
        Returns: (is_allowed, decision, details)
        """
        details = {"flags": [], "risk_score": 0.0}
        
        # Check 1: Amount limits
        if amount > self.booking_config.max_amount_per_booking:
            details["flags"].append("AMOUNT_EXCEEDS_LIMIT")
            details["risk_score"] = 1.0
            return False, "BLOCK", details
        
        # Check 2: Booking velocity (24h)
        since_24h = datetime.utcnow() - timedelta(hours=24)
        bookings_24h = self.db.query(Booking).filter(
            BookingModel.user_id == user_id,
            BookingModel.created_at >= since_24h
        ).count()
        
        if bookings_24h >= self.booking_config.max_bookings_per_user_24h:
            details["flags"].append("HIGH_VELOCITY_24H")
            details["risk_score"] += 0.4
        
        # Check 3: Booking velocity (7d)
        since_7d = datetime.utcnow() - timedelta(days=7)
        bookings_7d = self.db.query(Booking).filter(
            BookingModel.user_id == user_id,
            BookingModel.created_at >= since_7d
        ).count()
        
        if bookings_7d >= self.booking_config.max_bookings_per_user_7d:
            details["flags"].append("HIGH_VELOCITY_7D")
            details["risk_score"] += 0.3
        
        # Check 4: High value flag
        if amount >= self.booking_config.high_value_threshold:
            details["flags"].append("HIGH_VALUE")
            details["risk_score"] += 0.2
        
        # Determine decision
        decision = "ALLOW"
        if details["risk_score"] >= 0.7:
            decision = "BLOCK"
        elif details["risk_score"] >= 0.4:
            decision = "FLAG"
        
        # Log fraud check
        try:
            fraud_record = BookingFraudCheck(
                booking_id=booking_id or "pending",
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
    # TASK: WEBHOOK SUPPORT
    # =========================================================================
    
    def register_webhook(
        self,
        event_type: str,
        callback_url: str,
        secret: Optional[str] = None
    ) -> Dict:
        """Register webhook for booking events."""
        webhook_id = str(uuid.uuid4())
        webhook_secret = secret or str(uuid.uuid4())[:16]
        
        webhook = {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "callback_url": callback_url,
            "secret": webhook_secret,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self._webhook_registry[event_type].append(webhook)
        
        return {"success": True, "webhook_id": webhook_id, "secret": webhook_secret}

    async def trigger_webhooks(self, event_type: str, data: Dict) -> None:
        """Trigger webhooks for booking events."""
        webhooks = self._webhook_registry.get(event_type, [])
        
        for webhook in webhooks:
            if not webhook.get("active"):
                continue
            
            logger.info(f"📣 Would trigger webhook for {event_type}")
            
            # In production:
            # import httpx, hmac, hashlib
            # payload = json.dumps({"event": event_type, "data": data})
            # signature = hmac.new(webhook["secret"].encode(), payload.encode(), hashlib.sha256).hexdigest()
            # async with httpx.AsyncClient() as client:
            #     await client.post(webhook["callback_url"], json=payload, headers={"X-Signature": signature})

    # =========================================================================
    # MAIN BOOKING OPERATIONS
    # =========================================================================

    def create_booking(
        self,
        user_id: str,
        route_id: str,
        travel_date: str,
        booking_details: Dict,
        amount_paid: float,
        passenger_details_list: Optional[List[Dict]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Booking]:
        """Synchronous wrapper for scripts and legacy callers outside FastAPI's event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.create_booking_async(
                user_id=user_id,
                route_id=route_id,
                travel_date=travel_date,
                booking_details=booking_details,
                amount_paid=amount_paid,
                passenger_details_list=passenger_details_list,
                ip_address=ip_address,
                user_agent=user_agent,
            ))
        else:
            logger.error("create_booking called from a running event loop; use create_booking_async")
            return None

    async def create_booking_async(
        self,
        user_id: str,
        route_id: str,
        travel_date: str,
        booking_details: Dict,
        amount_paid: float,
        passenger_details_list: Optional[List[Dict]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[Booking]:
        """
        Create a booking with production features:
        - Idempotency
        - Distributed locking
        - Fraud detection
        - Audit logging
        - Webhook triggers
        """
        # Validate travel date
        travel_date_obj = validate_date_string(travel_date, allow_past=False)
        if not travel_date_obj:
            logger.error(f"Invalid travel date: {travel_date}")
            return None

        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(user_id, travel_date, route_id)
        
        # Check for existing booking (idempotency)
        existing = await self._check_idempotency(idempotency_key)
        if existing:
            logger.info(f"🎯 Idempotent booking found: {existing.pnr_number}")
            self._log_audit(
                booking_id=str(existing.id),
                pnr_number=existing.pnr_number,
                action="CREATE_IDEMPOTENT",
                new_state=existing.booking_status,
                actor_type="SYSTEM",
                amount=amount_paid,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return existing
        
        # Fraud check
        fraud_allowed, fraud_decision, fraud_details = self._check_fraud(user_id, amount_paid)
        if not fraud_allowed:
            self._log_audit(
                booking_id=None,
                pnr_number=None,
                action="FRAUD_BLOCK",
                new_state="BLOCKED",
                actor_type="SYSTEM",
                amount=amount_paid,
                extra_data={"fraud_details": fraud_details},
                ip_address=ip_address,
                user_agent=user_agent
            )
            logger.warning(f"🚨 Booking blocked for user {user_id}: fraud check failed")
            return None
        
        # Log fraud flag if applicable
        if fraud_decision == "FLAG":
            logger.warning(f"⚠️ Booking flagged for user {user_id}: {fraud_details.get('flags', [])}")
        
        # Acquire distributed lock
        lock_manager = self._get_lock_manager()
        lock_id = f"booking:{user_id}:{travel_date}"
        
        try:
            async def _do_locked_booking():
                async with lock_manager.lock(lock_id, self.LOCK_TIMEOUT_SECONDS):
                    existing_inner = await self._check_idempotency(idempotency_key)
                    if existing_inner:
                        return existing_inner
                    
                    return self._create_booking_internal(
                        user_id=user_id,
                        route_id=route_id,
                        travel_date_obj=travel_date_obj,
                        booking_details=booking_details,
                        amount_paid=amount_paid,
                        passenger_details_list=passenger_details_list,
                        idempotency_key=idempotency_key,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        fraud_decision=fraud_decision
                    )
            return await _do_locked_booking()
                
        except LockAcquisitionError as lock_err:
            logger.error(f"🔴 Lock acquisition failed: {lock_err}")
            logger.warning("⚠️ Proceeding without lock - potential duplicate risk")
            return self._create_booking_internal(
                user_id=user_id,
                route_id=route_id,
                travel_date_obj=travel_date_obj,
                booking_details=booking_details,
                amount_paid=amount_paid,
                passenger_details_list=passenger_details_list,
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                user_agent=user_agent,
                fraud_decision=fraud_decision
            )

    def _create_booking_internal(
        self,
        user_id: str,
        route_id: str,
        travel_date_obj: Any,
        booking_details: Dict,
        amount_paid: float,
        passenger_details_list: Optional[List[Dict]],
        idempotency_key: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        fraud_decision: str = "ALLOW"
    ) -> Optional[Booking]:
        """Internal booking creation with production features."""
        for attempt in range(self.MAX_RETRIES):
            try:
                from sqlalchemy import text
                assert self.db is not None
                db = self.db
                if db.bind is not None and db.bind.dialect.name not in ("sqlite", "sqlite3"):
                    db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
                
                # Generate unique PNR
                pnr_number = None
                for retry in range(10):
                    candidate_pnr = generate_pnr()
                    existing = self.db.query(Booking).filter(
                        BookingModel.pnr_number == candidate_pnr
                    ).first()
                    if not existing:
                        pnr_number = candidate_pnr
                        break
                
                if not pnr_number:
                    logger.error("Failed to generate unique PNR after 10 attempts")
                    return None
                
                # Check if booking already exists
                existing_booking = self.db.query(Booking).filter(
                    BookingModel.user_id == user_id,
                    BookingModel.travel_date == travel_date_obj,
                    BookingModel.booking_status.in_(["pending", "confirmed"])
                ).first()
                if existing_booking:
                    logger.warning(f"User {user_id} already has active booking for {travel_date_obj}")
                    self.db.rollback()
                    return existing_booking

                # Create booking with idempotency key
                booking = Booking(
                    pnr_number=pnr_number,
                    user_id=user_id,
                    route_id=route_id,
                    travel_date=travel_date_obj,
                    booking_status="pending",
                    amount_paid=amount_paid,
                    booking_details=booking_details,
                )
                self.db.add(booking)
                self.db.flush()
                self._persist_idempotency(idempotency_key, str(booking.id))

                route_info = booking_details.get('segments', [{}])[0] if booking_details.get('segments') else booking_details
                train_number = str(route_info.get('train_number') or route_info.get('trainNumber') or "")
                class_type = route_info.get('class_type') or route_info.get('class') or 'SL'
                quota = booking_details.get('quota') or route_info.get('quota') or 'GN'
                if train_number:
                    booking.train_number = train_number

                if train_number and not self.reserve_seat_inventory(booking, class_type=class_type, quota=quota):
                    self.db.rollback()
                    logger.warning(f"Seat inventory reservation failed for booking {pnr_number}")
                    return None
                
                # Add passenger details
                if passenger_details_list:
                    for pax_detail in passenger_details_list:
                        try:
                            passenger = PassengerDetails(
                                booking_id=booking.id,
                                full_name=pax_detail.get("full_name", pax_detail.get("name", "")),
                                age=pax_detail.get("age", 0),
                                gender=pax_detail.get("gender", "M"),
                                phone_number=pax_detail.get("phone_number"),
                                email=pax_detail.get("email"),
                                document_type=pax_detail.get("document_type"),
                                document_number=pax_detail.get("document_number"),
                                concession_type=pax_detail.get("concession_type"),
                                concession_discount=pax_detail.get("concession_discount", 0.0),
                                meal_preference=pax_detail.get("meal_preference"),
                            )
                            self.db.add(passenger)
                        except Exception as e:
                            logger.warning(f"Failed to add passenger details: {e}")
                
                self.db.commit()
                self.db.refresh(booking)

                # Cache idempotency result
                _schedule_background_task(
                    self._cache_idempotency(idempotency_key, str(booking.id)),
                    "booking idempotency cache",
                )

                route_info = {}
                train_class = 'SL'
                route_id = ""
                train_number = ""

                # [ALGORITHM_MVP] Integrate Dynamic Pricing Verification
                # Verify and update price with dynamic surge calculation
                try:
                    from services.deprecated.booking_price_calculator import get_booking_price_calculator
                    price_calc = get_booking_price_calculator(self.db)

                    if booking_details.get('segments'):
                        route_info = booking_details.get('segments', [{}])[0]

                    source = route_info.get('from', booking_details.get('source', ''))
                    dest = route_info.get('to', booking_details.get('destination', ''))
                    train_class = route_info.get('class', 'SL')
                    passenger_count = len(passenger_details_list) if passenger_details_list else 1
                    route_id = str(getattr(booking, 'route_id', None) or booking_details.get('route_id') or booking_details.get('routeId') or "")
                    train_number = str(route_info.get('train_number') or "")

                    price_breakdown = asyncio.run(price_calc.calculate_booking_price(
                        source=source,
                        destination=dest,
                        travel_date=travel_date_obj,
                        passenger_count=passenger_count,
                        train_class=train_class,
                        user_id=user_id,
                        route_id=route_id
                    ))
                    
                    # Update booking with price breakdown
                    if price_breakdown:
                        details = booking.booking_details or {}
                        booking.booking_details = details
                        details['price_breakdown'] = price_breakdown.to_dict()
                        details['surge_applied'] = price_breakdown.surge_multiplier
                        self.db.commit()
                        logger.info(f"Dynamic pricing applied: {price_breakdown.surge_multiplier}x surge")
                except Exception as pe:
                    logger.warning(f"Dynamic pricing integration failed: {pe}")

                # [ALGORITHM_MVP] Integrate Seat Allocation
                # Allocate seats based on passenger preferences
                try:
                    from services.inventory.allocator import get_booking_seat_allocator
                    seat_allocator = get_booking_seat_allocator(self.db)
                    
                    if passenger_details_list and train_number:
                        seat_result = asyncio.run(seat_allocator.allocate_seats_for_booking(
                            train_number=train_number,
                            travel_date=travel_date_obj,
                            passengers=passenger_details_list,
                            train_class=train_class,
                            quota=booking_details.get('quota', 'GN')
                        ))
                        
                        # Store seat allocation in booking details
                        if seat_result:
                            details = booking.booking_details or {}
                            booking.booking_details = details
                            details['seat_allocation'] = seat_result.to_dict()
                            self.db.commit()
                            logger.info(f"Seat allocation completed: {seat_result.message}")
                            
                        # Log seat allocation for analytics
                        try:
                            from services.data.algorithm_data import get_algorithm_data_service
                            data_service = get_algorithm_data_service(self.db)
                            for pax in passenger_details_list:
                                data_service.log_seat_allocation(
                                    booking_id=str(booking.id),
                                    passenger_id=pax.get('id', str(uuid.uuid4())),
                                    train_number=train_number,
                                    coach_id=seat_result.coach_assignments.get(pax.get('id', ''), 'UNKNOWN'),
                                    seat_number='TBD',
                                    preference_match=0.8,  # Simplified
                                    allocation_method='fair_distribution'
                                )
                        except Exception as ale:
                            logger.debug(f"Seat allocation logging failed: {ale}")
                except Exception as sae:
                    logger.warning(f"Seat allocation integration failed: {sae}")

                # [ALGORITHM_MVP] Record Booking Event for Demand Tracking
                try:
                    from services.data.algorithm_data import get_algorithm_data_service
                    data_service = get_algorithm_data_service(self.db)
                    
                    # Record booking event
                    data_service.record_booking_event(
                        source=str(route_info.get('from', '') or ''),
                        destination=str(route_info.get('to', '') or ''),
                        travel_date=travel_date_obj,
                        fare=amount_paid
                    )
                    
                    # Update user preferences
                    data_service.update_user_preferences(user_id, {
                        'source_code': str(route_info.get('from', '') or ''),
                        'destination_code': str(route_info.get('to', '') or ''),
                        'travel_date': travel_date_obj,
                        'created_at': datetime.utcnow()
                    })
                except Exception as be:
                    logger.debug(f"Booking event recording failed: {be}")

                # Log audit
                self._log_audit(
                    booking_id=str(booking.id),
                    pnr_number=pnr_number,
                    action="CREATE",
                    new_state="pending",
                    actor_type="USER",
                    actor_id=user_id,
                    amount=amount_paid,
                    extra_data={"fraud_decision": fraud_decision, "route_id": route_id},
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                logger.info(f"Booking created (pending): {pnr_number} on attempt {attempt + 1}")
                
                # Trigger webhooks
                _schedule_background_task(self.trigger_webhooks("booking.created", {
                    "booking_id": str(booking.id),
                    "pnr_number": pnr_number,
                    "user_id": user_id,
                    "amount": amount_paid,
                    "travel_date": travel_date_obj
                }), "booking.created webhook")

                # Fire-and-forget: publish booking event for analytics
                if Config.KAFKA_ENABLE_EVENTS:
                    try:
                        segments = booking_details.get('segments', [])
                        _schedule_background_task(
                            publish_booking_created(
                                user_id=user_id,
                                route_id=route_id,
                                total_cost=amount_paid,
                                segments=segments,
                                booking_reference=pnr_number
                            ),
                            "booking.created event",
                        )
                    except Exception as e:
                        logger.debug(f"Failed to publish booking event: {e}")

                return booking

            except DBAPIError as e:
                orig = getattr(e, 'orig', None)
                if orig is not None and hasattr(orig, 'pgcode') and getattr(orig, 'pgcode', None) == '40001':
                    logger.warning(f"Serialization failure on attempt {attempt + 1}. Retrying...")
                    self.db.rollback()
                    sleep(0.5 * (2 ** attempt))
                else:
                    logger.error(f"Database error during booking creation: {e}")
                    self.db.rollback()
                    return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during booking creation: {e}")
                self.db.rollback()
                return None
            finally:
                pass
        
        logger.error("Failed to create booking after multiple retries due to serialization failures.")
        return None

    def _init_monitoring(self, db: Session, booking: Booking):
        """Helper to initialize monitoring for a confirmed booking."""
        try:
            from database.models import BookingMonitor
            existing = db.query(BookingMonitor).filter(BookingMonitor.booking_id == booking.id).first()
            if not existing:
                new_monitor = BookingMonitor(
                    booking_id=booking.id,
                    user_id=booking.user_id,
                    pnr_number=booking.pnr_number,
                    train_number=booking.train_number,
                    travel_date=booking.travel_date,
                    is_monitoring_active=True,
                    alert_preferences={
                        "notify_on_delay_minutes": 30, 
                        "notify_on_cancellation": True,
                        "notify_on_pnr_change": True
                    }
                )
                db.add(new_monitor)
                logger.info(f"🛰️ Monitoring initialized for Booking {booking.id}")
        except Exception as e:
            logger.error(f"⚠️ Failed to init monitoring: {e}")

    def confirm_booking(self, booking_id: str, ip_address: Optional[str] = None) -> bool:
        """
        Confirm a pending booking (after payment is successful).
        With audit logging and webhook triggers.
        """
        try:
            booking = self.db.query(Booking).filter(BookingModel.id == booking_id).first()
            if not booking:
                logger.error(f"Booking not found: {booking_id}")
                return False
            
            previous_state = booking.booking_status
            
            # [REQ-016] Re-verify seat inventory before final confirmation
            from database.models import SeatInventory
            inventory = self.db.query(SeatInventory).filter(
                SeatInventory.locked_by_booking_id == booking_id
            ).first()
            
            if not inventory:
                # If lock was lost, try to re-acquire
                logger.warning(f"Inventory lock lost for booking {booking_id}. Attempting re-acquisition...")
                if not self.reserve_seat_inventory(booking):
                    logger.error(f"Failed to re-acquire seat for booking {booking_id}. Triggering refund.")
                    self.cancel_booking(booking_id, reason="Seat allocation failed during confirmation.")
                    return False
            elif inventory.locked_until and inventory.locked_until < datetime.utcnow():
                logger.warning(f"Inventory lock expired for booking {booking_id}. Refreshing lock...")
                inventory.locked_until = datetime.utcnow() + timedelta(minutes=30)
                self.db.flush()

            booking.booking_status = "confirmed"
            self._init_monitoring(self.db, booking)
            self.db.commit()
            
            # Log audit
            self._log_audit(
                booking_id=booking_id,
                pnr_number=booking.pnr_number,
                action="CONFIRM",
                new_state="confirmed",
                actor_type="SYSTEM",
                previous_state=previous_state,
                amount=booking.amount_paid,
                ip_address=ip_address
            )
            
            # Trigger webhooks
            _schedule_background_task(self.trigger_webhooks("booking.confirmed", {
                "booking_id": booking_id,
                "pnr_number": booking.pnr_number,
                "user_id": booking.user_id
            }), "booking.confirmed webhook")

            # Centralized Notification (Task 1.1.5)
            from services.communication.notification_service import notification_service
            
            async def notify_user():
                try:
                    # Notify via centralized service for audit trail
                    await notification_service.send_alert(
                        db=self.db,
                        user_id=str(booking.user_id),
                        title="Booking Confirmed! 🎫",
                        body=(
                            f"PNR: {booking.pnr_number}\n"
                            f"Train: {booking.train_number}\n"
                            f"Journey: {getattr(booking, 'source_station', 'N/A')} to {getattr(booking, 'destination_station', 'N/A')}\n"
                            f"Date: {getattr(booking, 'travel_date', 'N/A')}"
                        ),
                        alert_type="BOOKING_CONFIRMED",
                        booking_id=booking_id
                    )
                except Exception as ne:
                    logger.error(f"Notification failed for booking {booking_id}: {ne}")

            _schedule_background_task(notify_user(), "booking.confirmed notification")
            
            logger.info(f"Booking confirmed: {booking.pnr_number}")
            
            # PATENT-LEVEL: Record Conversion for ML Training
            try:
                from services.telemetry_service import record_conversion
                # search_id would ideally be in booking_details or state
                search_id = booking.booking_details.get("search_id") if booking.booking_details else None
                if search_id:
                    _schedule_background_task(
                        record_conversion(self.db, booking_id, search_id, float(booking.amount_paid)),
                        "booking conversion telemetry",
                    )
            except Exception as e:
                logger.error(f"Failed to record conversion: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to confirm booking: {e}")
            self.db.rollback()
            return False

    def cancel_booking(
        self,
        booking_id: str,
        reason: str = "",
        ip_address: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Cancel a booking with audit logging.
        """
        try:
            booking = self.db.query(Booking).filter(BookingModel.id == booking_id).first()
            if not booking:
                logger.error(f"Booking not found: {booking_id}")
                return False
            
            previous_state = booking.booking_status
            
            valid_actions = BookingStateMachine.get_valid_next_actions(booking)
            if "cancel" not in valid_actions:
                logger.error(f"Invalid transition: cancel is not allowed from current state {booking.booking_status}/{booking.escrow_status}")
                return False
            
            booking.booking_status = "cancelled"
            if getattr(booking, "escrow_status", None) != EscrowStatus.FAILED:
                booking.escrow_status = EscrowStatus.FAILED
            booking.escrow_message = reason or "Booking cancelled"
            self.release_seat_reservation(booking, commit=False)
            self.db.commit()
            
            # Log audit
            self._log_audit(
                booking_id=booking_id,
                pnr_number=booking.pnr_number,
                action="CANCEL",
                new_state="cancelled",
                actor_type=user_id or "SYSTEM",
                previous_state=previous_state,
                amount=booking.amount_paid,
                reason=reason,
                ip_address=ip_address
            )
            
            # Trigger webhooks
            _schedule_background_task(self.trigger_webhooks("booking.cancelled", {
                "booking_id": booking_id,
                "pnr_number": booking.pnr_number,
                "user_id": booking.user_id,
                "reason": reason
            }), "booking.cancelled webhook")

            # PATENT-LEVEL: SELF-HEALING REFUND
            # If booking was paid via Razorpay, initiate auto-refund
            try:
                from services.payment_service import PaymentService
                payment_service = PaymentService(self.db)
                # Find the captured payment for this booking
                payment = self.db.query(Payment).filter(
                    Payment.booking_id == booking_id,
                    Payment.status == "completed"
                ).first()
                
                if payment and payment.razorpay_payment_id:
                    logger.info(f"💸 Initiating auto-refund for cancelled booking {booking_id}")
                    _schedule_background_task(
                        payment_service.refund_payment(
                            payment_id=payment.razorpay_payment_id,
                            amount_rupees=booking.amount_paid,
                            reason=f"Auto-refund: {reason}",
                            user_id=str(getattr(booking, "user_id", ""))
                        ),
                        "booking cancellation refund",
                    )
            except Exception as re:
                logger.error(f"Auto-refund trigger failed for {booking_id}: {re}")

            logger.info(f"Booking cancelled: {booking.pnr_number} ({reason})")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel booking: {e}")
            self.db.rollback()
            return False

    def hold_seat(
        self,
        user_id: str,
        route_id: str,
        travel_date: str,
        booking_details: Dict,
        amount_paid: float,
    ) -> Optional[Booking]:
        """
        Creates a pending booking and reserves seat inventory if available.
        """
        try:
            travel_date_obj = validate_date_string(travel_date, allow_past=False)
            if not travel_date_obj:
                logger.error(f"Invalid travel date for seat hold: {travel_date}")
                return None

            booking = Booking(
                pnr_number=generate_pnr(),
                user_id=user_id,
                route_id=route_id,
                travel_date=travel_date_obj,
                booking_status="pending",
                amount_paid=amount_paid,
                booking_details=booking_details,
            )
            self.db.add(booking)
            self.db.flush()

            route_info = (booking_details or {}).get("segments", [{}])[0] if isinstance((booking_details or {}).get("segments"), list) else booking_details or {}
            class_type = route_info.get("class_type") or route_info.get("class") or "SL"
            quota = (booking_details or {}).get("quota") or route_info.get("quota") or "GN"
            booking.train_number = route_info.get("train_number") or booking.train_number

            if not self.reserve_seat_inventory(booking, class_type=class_type, quota=quota):
                self.db.rollback()
                logger.warning("Seat hold failed because inventory could not be reserved.")
                return None

            self.db.commit()
            self.db.refresh(booking)
            logger.info(f"Seat held. PNR: {booking.pnr_number}")
            return booking
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to hold seat: {e}")
            return None

    def create_pending_payment(
        self, booking: Booking, razorpay_order_id: str
    ) -> Optional[Payment]:
        """Create a pending payment record linked to a booking."""
        try:
            payment = Payment(
                booking_id=booking.id,
                razorpay_order_id=razorpay_order_id,
                status="pending",
                amount=booking.amount_paid,
            )
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
            logger.info(f"Pending payment record created for booking {booking.pnr_number}")
            return payment
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create pending payment: {e}")
            return None

    def get_booking_by_pnr(self, pnr: str) -> Optional[Booking]:
        """NEW: Get booking by PNR number."""
        try:
            booking = self.db.query(Booking).filter(
                BookingModel.pnr_number == pnr
            ).first()
            return booking
        except Exception as e:
            logger.error(f"Failed to fetch booking by PNR: {e}")
            return None

    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        """Get booking by primary key."""
        try:
            return self.db.query(Booking).filter(BookingModel.id == booking_id).first()
        except Exception as e:
            logger.error(f"Failed to fetch booking by ID: {e}")
            return None

    def get_user_bookings(
        self, 
        user_id: Optional[str] = None, 
        telegram_chat_id: Optional[str] = None,
        skip: int = 0, 
        limit: int = 20,
        status_filter: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Tuple[List[Booking], int]:
        """Get bookings for a user or telegram chat with pagination."""
        try:
            query = self.db.query(Booking)
            
            if user_id:
                query = query.filter(BookingModel.user_id == user_id)
            elif telegram_chat_id:
                # Find linked user
                from services.user_service import UserService
                user_service = UserService(self.db)
                # Note: using synchronous version or run_in_executor if needed
                # For now, let's look up directly
                user = self.db.query(User).filter(User.telegram_id == telegram_chat_id).first()
                if not user:
                    # Try TelegramAccount
                    from database.models import TelegramAccount
                    account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == telegram_chat_id).first()
                    if account:
                        query = query.filter(BookingModel.user_id == account.user_id)
                    else:
                        return [], 0
                else:
                    query = query.filter(BookingModel.user_id == user.id)
            else:
                return [], 0

            if status_filter:
                query = query.filter(BookingModel.booking_status == status_filter)
            if from_date:
                query = query.filter(BookingModel.travel_date >= from_date)
            if to_date:
                query = query.filter(BookingModel.travel_date <= to_date)
                
            total = query.count()
            bookings = query.order_by(BookingModel.created_at.desc()).offset(skip).limit(limit).all()
            return bookings, total
        except Exception as e:
            logger.error(f"Failed to fetch user bookings: {e}")
            return [], 0

    def update_booking_status(self, booking_id: str, new_status: str) -> Optional[Booking]:
        """Update booking status and return the updated row."""
        try:
            booking = self.get_booking_by_id(booking_id)
            if not booking:
                return None
            booking.booking_status = new_status
            self.db.commit()
            self.db.refresh(booking)
            return booking
        except Exception as e:
            logger.error(f"Failed to update booking status: {e}")
            self.db.rollback()
            return None

    def confirm_booking_payment(
        self, order_id: str, payment_id: str, payment_status: str
    ) -> bool:
        """
        Find booking by razorpay_order_id and update it with payment details.
        This is called by the webhook and is designed to be idempotent.
        """
        try:
            payment = self.db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
            if not payment:
                logger.warning(f"Payment record not found for order_id: {order_id}")
                return False

            normalized_status = str(payment_status).strip().lower()
            if payment.status == "completed" and normalized_status in {"completed", "success"}:
                logger.warning(f"Payment for order_id: {order_id} has already been completed. Ignoring webhook event.")
                return True

            payment.razorpay_payment_id = payment_id
            payment.status = "completed" if normalized_status in {"completed", "success"} else payment_status

            booking = self.db.query(Booking).filter(BookingModel.id == payment.booking_id).first()
            if not booking:
                logger.error(f"CRITICAL: Booking not found for payment {payment.id}, but payment was made!")
                self.db.commit()
                return False

            booking.payment_status = payment.status

            if normalized_status in {"completed", "success"}:
                booking.escrow_status = EscrowStatus.COMPLETED
                booking.escrow_message = "Payment completed through webhook."
                self.db.commit()
                if booking.booking_status != "confirmed":
                    return self.confirm_booking(str(getattr(booking, "id", "")))
                return True

            if normalized_status in {"failed", "cancelled"}:
                booking.escrow_status = EscrowStatus.FAILED
                booking.escrow_message = "Payment failed or was cancelled."
            elif normalized_status == "refunded":
                booking.escrow_status = EscrowStatus.REFUNDED
                booking.escrow_message = "Payment refunded."

            self.db.commit()
            logger.info(f"Booking {booking.id} payment confirmed with status '{payment.status}'")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update booking payment status: {e}")
            return False

    def reserve_seat_inventory(
        self,
        booking: Booking,
        class_type: Optional[str] = None,
        quota: str = "GN",
        hold_minutes: int = 30
    ) -> bool:
        """Reserve a seat from SeatInventory for a pending booking."""
        try:
            from database.models import SeatInventory

            class_type = class_type or (booking.booking_details or {}).get("class_type") or (booking.booking_details or {}).get("class") or "SL"
            from_station = (booking.booking_details or {}).get("from_station_code") or (booking.booking_details or {}).get("from")
            to_station = (booking.booking_details or {}).get("to_station_code") or (booking.booking_details or {}).get("to")
            travel_date = booking.travel_date

            if not booking.train_number or not travel_date or not from_station or not to_station:
                logger.warning("Insufficient route information to reserve seat inventory.")
                return False

            inventory = self.db.query(SeatInventory).filter(
                SeatInventory.train_number == booking.train_number,
                SeatInventory.from_station_code == from_station,
                SeatInventory.to_station_code == to_station,
                SeatInventory.travel_date == travel_date,
                SeatInventory.class_type == class_type,
                SeatInventory.quota == quota,
                SeatInventory.available_seats > 0
            ).first()

            if not inventory:
                logger.warning(f"No available inventory for train {booking.train_number} on {travel_date}")
                return False

            inventory.available_seats = max(inventory.available_seats - 1, 0)
            inventory.locked_until = datetime.utcnow() + timedelta(minutes=hold_minutes)
            inventory.locked_by_booking_id = booking.id
            inventory.last_updated = datetime.utcnow()
            self.db.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to reserve seat inventory: {e}")
            self.db.rollback()
            return False

    def release_seat_reservation(self, booking: Booking, commit: bool = True) -> bool:
        """Release any seat inventory reserved for the canceled booking."""
        try:
            from database.models import SeatInventory

            inventory = self.db.query(SeatInventory).filter(
                SeatInventory.locked_by_booking_id == booking.id
            ).first()
            if not inventory:
                return False

            inventory.available_seats = max(inventory.available_seats + 1, 0)
            inventory.locked_by_booking_id = None
            inventory.locked_until = None
            inventory.last_updated = datetime.utcnow()
            if commit:
                self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to release seat inventory: {e}")
            if commit:
                self.db.rollback()
            return False

    def cleanup_expired_locks(self) -> int:
        """
        Housekeeping: Release seats that were locked but never paid for.
        Called by background cron or orchestrator.
        """
        try:
            from database.models import SeatInventory
            now = datetime.utcnow()
            expired = self.db.query(SeatInventory).filter(
                SeatInventory.locked_until < now,
                SeatInventory.locked_by_booking_id.is_not(None)
            ).all()
            
            count = 0
            for inv in expired:
                # Double check booking status
                booking = self.get_booking_by_id(str(inv.locked_by_booking_id))
                if not booking or booking.booking_status == "pending":
                    inv.available_seats += 1
                    inv.locked_by_booking_id = None
                    inv.locked_until = None
                    inv.last_updated = now
                    count += 1
            
            if count > 0:
                self.db.commit()
                logger.info(f"🧹 Cleaned up {count} expired seat locks.")
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup expired seat locks: {e}")
            self.db.rollback()
            return 0


    def get_booking(self, booking_id: str, user: User) -> Optional[Booking]:
        """Get a single booking for a user."""
        try:
            booking = self.db.query(Booking).filter(BookingModel.id == booking_id, BookingModel.user_id == user.id).first()
            return booking
        except Exception as e:
            logger.error(f"Failed to get booking: {e}")
            return None

    def get_bookings_by_user(self, user: User) -> List[Booking]:
        """Get all bookings for a specific user, eagerly loading route details."""
        try:
            bookings = (
                self.db.query(Booking)
                .options(joinedload(BookingModel.route))
                .filter(BookingModel.user_id == user.id)
                .order_by(BookingModel.created_at.desc())
                .all()
            )
            return bookings
        except Exception as e:
            logger.error(f"Failed to get bookings for user {user.id}: {e}")
            return []

    def get_user_booking_for_route_date(
        self, user_id: str, route_id: str, travel_date: str
    ) -> Optional[Booking]:
        """Retrieve a booking for a specific user, route, and travel date."""
        try:
            return self.db.query(Booking).filter(
                BookingModel.user_id == user_id,
                BookingModel.route_id == route_id,
                BookingModel.travel_date == travel_date
            ).first()
        except Exception as e:
            logger.error(f"Failed to get booking for user {user_id}, route {route_id}, date {travel_date}: {e}")
            return None

    def is_booking_payment_completed(
        self, user_id: str, route_id: str, travel_date: str
    ) -> bool:
        """Check if a booking's payment status is 'completed' for a user, route, and date."""
        try:
            booking = self.get_user_booking_for_route_date(user_id, route_id, travel_date)
            return booking is not None and getattr(booking, "payment_status", None) == "completed"
        except Exception as e:
            logger.error(f"Failed to check booking payment status: {e}")
            return False

    def get_booking_stats(self) -> Dict[str, Any]:
        """
        Calculates booking statistics, including total revenue and revenue per transport mode.
        Resolves N+1 queries by eager loading related data.
        """
        stats: Dict[str, Any] = {
            "total_bookings": 0,
            "completed_bookings": 0,
            "pending_bookings": 0,
            "total_revenue": 0.0,
            "revenue_by_mode": {},
            "top_routes_by_revenue": [], # Placeholder for future enhancement
        }

        # Fetch bookings with related Route and Segments eagerly loaded
        bookings = self.db.query(Booking).options(
            joinedload(BookingModel.route) # Eager load the Route associated with the Booking
        ).filter(BookingModel.payment_status == "completed").all() # Only consider completed bookings for revenue

        for booking in bookings:
            stats["total_bookings"] += 1 # This counts all bookings, including non-completed
            stats["completed_bookings"] += 1
            stats["total_revenue"] += booking.amount_paid

            booking_route = getattr(booking, "route", None)
            if booking_route and booking_route.segments:
                # Assuming route.segments is a list of dicts from the JSON column
                # and each dict has a 'mode' key.
                # For simplicity, if a route is multi-modal, we attribute the full revenue
                # to the mode of its first segment for "Revenue per Mode" report.
                # A more accurate model would distribute revenue per segment.
                if booking_route.segments:
                    first_segment_mode = booking_route.segments[0].get("mode", "unknown")
                    stats["revenue_by_mode"].setdefault(first_segment_mode, 0.0)
                    stats["revenue_by_mode"][first_segment_mode] += booking.amount_paid
            
            # Increment pending bookings count separately if needed,
            # but current query only fetches completed for revenue.
            # To get full stats, would need to query all bookings then filter or two queries.

        # For pending bookings, fetch separately or adjust initial query
        stats["pending_bookings"] = self.db.query(Booking).filter(
            BookingModel.payment_status == "pending"
        ).count()
        stats["total_bookings"] = self.db.query(Booking).count()


        return stats

    def get_booking_velocity(self, train_number: str, hours: int = 24) -> float:
        """
        Calculate booking velocity (bookings per hour) for a specific train.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        count = self.db.query(Booking).filter(
            BookingModel.train_number == train_number,
            BookingModel.created_at >= since
        ).count()
        return count / hours if hours > 0 else 0.0

    def create_escrow_booking(
        self,
        user_id: str,
        passenger_name: str,
        passenger_age: int,
        train_number: str,
        amount: float,
    ) -> Optional[Booking]:
        """
        Initialize a booking in CREATED escrow status.
        """
        from database.models import EscrowStatus
        import uuid
        
        upi_tx_id = f"TX{int(datetime.utcnow().timestamp())}{uuid.uuid4().hex[:6].upper()}"
        
        booking = Booking(
            user_id=user_id,
            train_number=train_number,
            amount_paid=amount,
            escrow_status=EscrowStatus.CREATED,
            upi_tx_id=upi_tx_id,
            booking_status="pending",
            travel_date=date.today() # Fallback
        )
        self.db.add(booking)
        self.db.flush()
        
        passenger = PassengerDetails(
            booking_id=booking.id,
            full_name=passenger_name,
            age=passenger_age,
            gender="M" # Default
        )
        self.db.add(passenger)
        self.db.commit()
        self.db.refresh(booking)
        return booking

    def submit_utr(self, booking_id: str, utr_number: str) -> Optional[Booking]:
        """
        Submit UTR for a booking and transition to UTR_SUBMITTED.
        """
        from database.models import EscrowStatus
        booking = self.db.query(Booking).filter(BookingModel.id == booking_id).first()
        if not booking:
            return None
            
        if not (hasattr(booking, "validate_escrow_transition") and cast(Any, booking).validate_escrow_transition(EscrowStatus.UTR_SUBMITTED)):
            logger.error(f"Invalid transition to UTR_SUBMITTED from {getattr(booking, 'escrow_status', 'unknown')}")
            return booking

        # Check if UTR already exists
        existing = self.db.query(Booking).filter(BookingModel.utr_number == utr_number).first()
        if existing:
            raise ValueError("UTR already submitted for another booking")

        setattr(booking, "utr_number", utr_number)
        booking.escrow_status = EscrowStatus.UTR_SUBMITTED
        self.db.commit()
        self.db.refresh(booking)
        
        # Trigger background verification (Mock for now)
        _schedule_background_task(
            self._mock_escrow_verification(str(getattr(booking, 'id'))),
            "escrow verification",
        )
        
        return booking

    async def _mock_escrow_verification(self, booking_id: str):
        """
        Simulate background escrow verification and booking.
        """
        from database.models import EscrowStatus
        from sqlalchemy.orm import sessionmaker
        from database import engine
        
        # Need a new session for background task
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            await asyncio.sleep(5) # Wait 5 seconds
            booking = db.query(Booking).filter(BookingModel.id == booking_id).first()
            if booking and booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
                booking.escrow_status = EscrowStatus.VERIFIED
                db.commit()
                
                await asyncio.sleep(5)
                booking.escrow_status = EscrowStatus.BOOKING_INITIATED
                db.commit()
                
                await asyncio.sleep(10)
                booking.escrow_status = EscrowStatus.COMPLETED
                booking.pnr_number = generate_pnr()
                booking.booking_status = "confirmed"
                
                # Mock usage of the monitor helper
                from database.models import BookingMonitor
                existing = db.query(BookingMonitor).filter(BookingMonitor.booking_id == booking_id).first()
                if not existing:
                    new_monitor = BookingMonitor(
                        booking_id=booking.id,
                        user_id=booking.user_id,
                        pnr_number=booking.pnr_number,
                        train_number=booking.train_number,
                        travel_date=booking.travel_date,
                        is_monitoring_active=True,
                        alert_preferences={"notify_on_delay_minutes": 30, "notify_on_cancellation": True}
                    )
                    db.add(new_monitor)
                
                db.commit()
        except Exception as e:
            logger.error(f"Error in mock verification: {e}")
        finally:
            db.close()

    # =========================================================================
    # ALGORITHM_MVP: PRICE QUOTE INTEGRATION
    # =========================================================================

    async def get_price_quote(
        self,
        source: str,
        destination: str,
        travel_date: str,
        passenger_count: int,
        train_class: str = "SL",
        user_id: str = "anonymous"
    ) -> Dict[str, Any]:
        """
        Get dynamic price quote with all integrations.
        Uses the Booking Integration Orchestrator for complete pricing.
        
        Args:
            source: Source station code
            destination: Destination station code
            travel_date: Travel date (YYYY-MM-DD)
            passenger_count: Number of passengers
            train_class: Train class (SL, 3A, 2A, 1A, etc.)
            user_id: User ID for personalization
            
        Returns:
            Dict with price breakdown and metadata
        """
        try:
            from datetime import date as date_type
            from services.booking_integration_orchestrator import quick_quote
            
            # Parse travel date
            travel_date_obj = date_type.fromisoformat(travel_date)
            
            # Get quick quote
            quote = await quick_quote(
                source=source,
                destination=destination,
                travel_date=travel_date_obj,
                passenger_count=passenger_count,
                train_class=train_class,
                user_id=user_id
            )
            
            return {
                "status": "success",
                "quote": quote
            }
            
        except Exception as e:
            logger.error(f"Price quote generation failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "redis": self._redis_breaker.get_metrics(),
                "database": self._db_breaker.get_metrics(),
                "kafka": self._kafka_breaker.get_metrics()
            },
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._redis_breaker.reset()
        self._db_breaker.reset()
        self._kafka_breaker.reset()
        logger.info("All circuit breakers reset for booking_service")

booking_service = BookingService()
