import logging
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import User, IdentityFingerprint, FraudAlert, RouteSearchLog
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy
from collections import deque

logger = logging.getLogger("fraud-service")

TRAVEL_RADIUS_THRESHOLD_KM = 500 # Max movement in 1 hour
MAX_ACCOUNTS_PER_DEVICE = 3


class FraudServiceMetrics:
    """Metrics tracking for fraud service."""

    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

    async def record_fraud_check(self, check_type: str, result: str, success: bool):
        """Record fraud check metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "check_type": check_type,
                "result": result,
                "success": success
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_checks": 0, "alerts_generated": 0}

        total = len(self._metrics)
        alerts = sum(1 for m in self._metrics if m["result"] in ["SYBIL_ATTACK", "IMPOSSIBLE_TRAVEL"])
        by_type = {}
        for m in self._metrics:
            check_type = m.get("check_type", "unknown")
            if check_type not in by_type:
                by_type[check_type] = {"total": 0, "alerts": 0}
            by_type[check_type]["total"] += 1
            if m["result"] in ["SYBIL_ATTACK", "IMPOSSIBLE_TRAVEL"]:
                by_type[check_type]["alerts"] += 1

        return {
            "total_checks": total,
            "alerts_generated": alerts,
            "by_type": by_type
        }


class FraudService:
    """Fraud detection service with resilience patterns."""

    def __init__(self):
        # Circuit breakers
        self._redis_breaker = circuit_breaker_manager.get_or_create(
            "fraud_redis",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "fraud_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=60.0, success_threshold=2)
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
            initial_delay=0.1,
            max_delay=5.0,
            conditions=[
                lambda e: "connection" in str(e).lower()
            ]
        )

        # Metrics tracking
        self._metrics = FraudServiceMetrics()

        logger.info("FraudService initialized with resilience patterns")

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "redis": self._redis_breaker.get_metrics().to_dict(),
                "database": self._db_breaker.get_metrics().to_dict()
            },
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._redis_breaker.reset()
        self._db_breaker.reset()
        logger.info("All circuit breakers reset for fraud_service")

    @staticmethod
    def generate_fingerprint(client_ip: str, user_agent: str, device_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        [Task 45.A] High-Entropy Fingerprinting.
        Combines IP, UA, and Browser Metadata (Canvas/WebGL hashes from frontend).
        """
        meta_str = str(device_metadata or {})
        seed = f"{client_ip}|{user_agent}|{meta_str}"
        return hashlib.sha256(seed.encode()).hexdigest()

    @staticmethod
    async def validate_identity(db: Session, user: User, client_ip: str, user_agent: str, background_tasks=None, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        [Task 45.B HARDENING] Atomic Sybil Detection + Background Persistence.
        """
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.initialize()
        redis = multi_layer_cache.redis
        if redis is None:
            raise RuntimeError("Redis unavailable for fraud validation")
        
        fp_hash = FraudService.generate_fingerprint(client_ip, user_agent, metadata)
        
        # 1. Atomic LUA script to prevent orphaned keys (INCR + EXPIRE)
        lua_script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return current
        """
        redis_key = f"fp_count:{fp_hash}"
        device_users = await redis.eval(lua_script, 1, redis_key, 86400)

        if device_users > MAX_ACCOUNTS_PER_DEVICE:
            FraudService.create_alert(db, user.id, "SYBIL_ATTACK", "CRITICAL", {"accounts": device_users})
            await FraudService.revoke_session(user.id)
            return 1.0
            
        # 2. [Task 45.F] Async Background Persistence
        if user.last_fingerprint != fp_hash:
            user.last_fingerprint = fp_hash
            if background_tasks:
                # Move DB write off the request thread
                background_tasks.add_task(FraudService._persist_fingerprint, user.id, fp_hash)
            else:
                db.commit()
            
        return 0.0

    @staticmethod
    def _persist_fingerprint(user_id: str, fp_hash: str):
        """Background Sync for Fingerprint."""
        from database.session import SessionLocal
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.last_fingerprint = fp_hash
                db.commit()
                logger.info(f"Background Sync: Fingerprint updated for {user_id}")

    @staticmethod
    async def revoke_session(user_id: str):
        """
        [Task 45.C] Immediate Session Revocation using Redis Blacklist.
        """
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.initialize()
        redis = multi_layer_cache.redis
        if redis is None:
            raise RuntimeError("Redis unavailable for session revocation")
        # Push user_id to blacklist for 1 hour
        await redis.setex(f"blacklist:user:{user_id}", 3600, "BANNED")
        logger.error(f"🚫 Session Revoked for High Risk User: {user_id}")

    @staticmethod
    def check_impossible_travel(db: Session, user_id: str, current_city: str):
        """
        [Task 45.2] Detects impossible user movement.
        """
        last_log = db.query(RouteSearchLog).filter(
            RouteSearchLog.user_id == user_id
        ).order_by(RouteSearchLog.timestamp.desc()).first()
        
        if not last_log: return
        
        # Simplified Check: Just check time difference if city changes
        # Correct implementation would use Geo-distance
        time_diff = datetime.utcnow() - last_log.timestamp
        if last_log.origin_city != current_city and time_diff < timedelta(minutes=15):
            FraudService.create_alert(db, user_id, "IMPOSSIBLE_TRAVEL", "HIGH", {
                "prev": last_log.origin_city, 
                "current": current_city
            })

    @staticmethod
    def create_alert(db: Session, user_id: str, alert_type: str, severity: str, metadata: dict):
        alert = FraudAlert(
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            metadata_json=metadata
        )
        db.add(alert)
        db.commit()
        logger.error(f"🚨 FRAUD ALERT [{severity}]: User {user_id} - {alert_type}")

fraud_service = FraudService()
