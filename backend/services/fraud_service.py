import logging
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import User, IdentityFingerprint, FraudAlert, RouteSearchLog

logger = logging.getLogger("fraud-service")

TRAVEL_RADIUS_THRESHOLD_KM = 500 # Max movement in 1 hour
MAX_ACCOUNTS_PER_DEVICE = 3

class FraudService:
    @staticmethod
    def generate_fingerprint(client_ip: str, user_agent: str, device_metadata: dict = None) -> str:
        """
        [Task 45.A] High-Entropy Fingerprinting.
        Combines IP, UA, and Browser Metadata (Canvas/WebGL hashes from frontend).
        """
        meta_str = str(device_metadata or {})
        seed = f"{client_ip}|{user_agent}|{meta_str}"
        return hashlib.sha256(seed.encode()).hexdigest()

    @staticmethod
    async def validate_identity(db: Session, user: User, client_ip: str, user_agent: str, background_tasks=None, metadata: dict = None) -> float:
        """
        [Task 45.B HARDENING] Atomic Sybil Detection + Background Persistence.
        """
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.initialize()
        redis = multi_layer_cache.redis
        
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
        # Push user_id to blacklist for 1 hour
        await multi_layer_cache.redis.setex(f"blacklist:user:{user_id}", 3600, "BANNED")
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
