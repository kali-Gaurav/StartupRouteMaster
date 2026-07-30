
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Request, Depends, status
from sqlalchemy.orm import Session
from microservices.shared.config import Config
from database.session import get_db, with_db_retry

logger = logging.getLogger("shared-auth")

class SharedAuthManager:
    """
    [CONSOLIDATED] FAANG-level Authentication & Session Management.
    Single Source of Truth for all Auth Logic across Monolith and Microservices.
    """
    def __init__(self, db: Session, redis_client: Optional[Any] = None):
        self.db = db
        self.redis = redis_client
        
        try:
            from core.auth.supabase_client import supabase
            self.supabase = supabase
        except ImportError:
            self.supabase = None

    async def check_rate_limit(self, key: str, limit: int = 5, window: int = 60) -> bool:
        """Sliding window rate limiter."""
        if not self.redis: return True
        try:
            # Note: For sync compatibility in monolith, we might need a sync wrapper
            # But here we assume async usage in new services
            count = await self.redis.get(f"auth:limit:{key}")
            if count and int(count) >= limit: return False
            await self.redis.incr(f"auth:limit:{key}")
            if not count: await self.redis.expire(f"auth:limit:{key}", window)
            return True
        except: return True

    def is_blacklisted(self, token: str) -> bool:
        """Check if token is in Redis blacklist (Sync)."""
        try:
            from services.multi_layer_cache import multi_layer_cache
            return multi_layer_cache.get_sync(f"auth:blacklist:{token}") is not None
        except Exception as e:
            logger.error(f"Blacklist check failed: {e}")
            return False

    def blacklist_token(self, token: str, expires_in: int):
        """Add token to Redis blacklist (Sync)."""
        try:
            from services.multi_layer_cache import multi_layer_cache
            multi_layer_cache.set_sync(f"auth:blacklist:{token}", "revoked", ttl=expires_in)
            logger.info(f"Token blacklisted for {expires_in}s")
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")

    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """Strict JWT verification with Supabase + Blacklist check."""
        # 1. Check Blacklist first (fast, local/redis)
        if self.is_blacklisted(token):
            logger.warning("Attempted use of blacklisted token.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer", "X-Error-Code": "TOKEN_REVOKED"}
            )

        if not self.supabase:
            raise HTTPException(status_code=500, detail="Supabase not configured")

        try:
            resp = self.supabase.auth.get_user(token)
            user = getattr(resp, "user", None) or (resp.get("user") if isinstance(resp, dict) else None)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid session")
            return user
        except Exception as e:
            logger.error(f"JWT Verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    @with_db_retry()
    def sync_user(self, sb_user: Any) -> Any:
        """Synchronize Firebase user to PostgreSQL."""
        from database.models import User, Profile
        sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
        sb_email = getattr(sb_user, "email", sb_user.get("email") if isinstance(sb_user, dict) else None)
        sb_metadata = getattr(sb_user, "user_metadata", sb_user.get("user_metadata", {}) if isinstance(sb_user, dict) else {})
        sb_role = sb_metadata.get("role") or "user"
        
        user = self.db.query(User).filter(User.firebase_uid == sb_id).first()
        if not user:
            # Logic from old auth_manager.py
            sb_name = sb_metadata.get("full_name") or sb_metadata.get("name") or (sb_email.split('@')[0] if sb_email else "User")
            user = User(
                email=sb_email,
                firebase_uid=sb_id,
                role=sb_role,
                full_name=sb_name,
                is_verified=True
            )
            self.db.add(user)
            self.db.flush()
            
            profile = Profile(user_id=user.id, name=sb_name)
            self.db.add(profile)
            self.db.commit()
            self.log_audit(user.id, "USER_CREATED", reason="Sync from Firebase")
        elif user.role != sb_role:
            user.role = sb_role
            self.db.commit()
            
        return user

    @with_db_retry()
    def track_session(self, user_id: str, request: Request, refresh_token: str = None) -> str:
        """Advanced Session Tracking with Fingerprinting."""
        from database.models import UserSession
        client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")
        if "," in client_ip: client_ip = client_ip.split(",")[0].strip()
        user_agent = request.headers.get("user-agent", "unknown")
        
        device_type = "Mobile" if any(m in user_agent for m in ["Mobile", "Android", "iPhone"]) else "Desktop"
        device_info = {"type": device_type, "ua": user_agent[:100], "ip": client_ip}
        
        # Session Rotation logic
        existing = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.ip_address == client_ip,
            UserSession.user_agent == user_agent,
            UserSession.is_active == True
        ).first()
        
        if existing and (datetime.utcnow() - existing.last_seen_at).total_seconds() < 3600:
            existing.last_seen_at = datetime.utcnow()
            self.db.commit()
            return existing.id

        new_session = UserSession(
            user_id=user_id, ip_address=client_ip, user_agent=user_agent,
            device_info=device_info, is_active=True, login_at=datetime.utcnow()
        )
        if refresh_token:
            new_session.refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            
        self.db.add(new_session)
        self.db.commit()
        return new_session.id

    def get_active_sessions(self, user_id: str) -> List[Any]:
        from database.models import UserSession
        return self.db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.is_active == True).all()

    def revoke_session(self, session_id: str, user_id: str):
        from database.models import UserSession
        session = self.db.query(UserSession).filter(UserSession.id == session_id, UserSession.user_id == user_id).first()
        if session:
            session.is_active = False
            self.db.commit()
            return True
        return False

    def revoke_all_sessions(self, user_id: str):
        from database.models import UserSession
        sessions = self.get_active_sessions(user_id)
        for s in sessions: s.is_active = False
        self.db.commit()
        return len(sessions)

    def enforce_verification(self, user: Any):
        if not user.is_verified and Config.ENVIRONMENT != "development":
            raise HTTPException(status_code=403, detail="Account verification required.")

    def log_audit(self, user_id: str, action: str, reason: str = None):
        from database.models import AuditLog
        audit = AuditLog(entity_type="AUTH", entity_id=user_id, action=action, performed_by=user_id, reason=reason)
        self.db.add(audit)
        self.db.commit()

    async def detect_anomaly(self, user_id: str, request: Request) -> bool:
        from database.models import UserSession
        client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")
        last_session = self.db.query(UserSession).filter(UserSession.user_id == user_id).order_by(UserSession.login_at.desc()).first()
        if last_session and last_session.ip_address != client_ip:
            self.log_audit(user_id, "ANOMALY_DETECTED", reason=f"New IP: {client_ip}")
            return True
        return False
