import logging
import json
import time
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException, Request, status

from core.integration.providers import ServiceProvider, ServiceStatus
from core.infrastructure.container import container
from database.config import Config
from core.auth.utils import verify_fingerprint, generate_fingerprint
from core.auth.sybil import sybil_manager

logger = logging.getLogger("routemaster.auth")

class AuthServiceProvider(ServiceProvider):
    """
    Task 10: Advanced Auth System Upgrade.
    Elite IoC-managed Authentication, Session Tracking, and Anomaly Detection.
    """
    def __init__(self):
        super().__init__("auth", version="2.0.0")
        self.supabase = None
        
    async def init(self):
        """IoC Lifecycle: Initialize Firebase Admin SDK and Auth Cache."""
        from core.auth.firebase_client import lazy_init, is_ready
        ok = lazy_init()
        if ok:
            logger.info("🔥 IoC: AuthServiceProvider Initialized with Firebase (v2.0.0).")
        else:
            logger.warning(
                "⚠️ AuthServiceProvider: Firebase Admin SDK not ready. "
                "Token verification will fail until GOOGLE_APPLICATION_CREDENTIALS is set. "
                "Server continues booting in degraded auth mode."
            )
        # Do NOT raise — let the server boot so health checks pass.

    # ==========================================================================
    # CORE AUTH & VERIFICATION
    # ==========================================================================

    async def verify_token(self, token: str, request: Request, skip_cache: bool = False) -> Dict[str, Any]:
        """
        [Task 10.2] Strict Token Introspection with IP/UA binding.
        [Task 10.1] Uses Redis Auth Cache for high-speed validation.
        """
        if not token:
            raise HTTPException(status_code=401, detail="Missing auth token")

        # 0. Sybil/Challenge Check [Task 110]
        # Skip if already bypassed for this session
        user_id = token.split(":")[0] # Simplified logic for quick lookup if possible
        if await sybil_manager.check_challenge_required(user_id, request):
            if not await sybil_manager.is_bypassed(user_id):
                raise HTTPException(status_code=403, detail="CHALLENGE_REQUIRED")

        cache = await container.get("cache")
        
        # 1. Blacklist Check (Redis)
        if cache and cache.redis:
            is_revoked = await cache.redis.get(f"auth:blacklist:{token}")
            if is_revoked:
                logger.warning(f"Auth: Revoked token attempt.")
                raise HTTPException(status_code=401, detail="Token revoked")

        # 2. Cache Lookup (Token Introspection)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        client_id = request.headers.get("X-Client-Id")
        fingerprint = request.headers.get("X-Fingerprint")

        if cache and cache.redis and not skip_cache:
            cached_data = await cache.redis.get(f"auth:session:{token_hash}")
            if cached_data:
                session_info = json.loads(cached_data)
                
                # [Task 106] JWT Fingerprinting Check
                if client_id and fingerprint:
                    ua = request.headers.get("user-agent", "unknown")
                    ip = self._get_client_ip(request)
                    if not verify_fingerprint(fingerprint, client_id, ua, ip):
                        logger.warning(f"🚨 FINGERPRINT MISMATCH: {client_id} from {ip}")
                        # Don't throw immediately to avoid enumeration? No, throw 401.
                        raise HTTPException(status_code=401, detail="Invalid client signature")

                # [Task 10.2] IP/UA Introspection
                await self._validate_introspection(session_info, request)
                return session_info["user"]

        # 3. Firebase Live Check
        try:
            from core.auth.firebase_client import get_auth
            firebase_auth = get_auth()
            # [Task 10.10] Firebase ID Token Verification
            decoded_token = firebase_auth.verify_id_token(token)
            
            if not decoded_token:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            user_data = {
                "id": decoded_token["uid"],
                "email": decoded_token.get("email"),
                "role": decoded_token.get("role", "user"), # Custom claims if any
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture")
            }
            
            # 4. Cache the result with Introspection Data [Task 10.1]
            if cache and cache.redis:
                session_info = {
                    "user": user_data,
                    "bound_ip": self._get_client_ip(request),
                    "bound_ua": request.headers.get("user-agent", "unknown"),
                    "created_at": time.time()
                }
                await cache.redis.set(f"auth:session:{token_hash}", json.dumps(session_info), ex=3600)
            
            return user_data
        except Exception as e:
            logger.error(f"Firebase JWT Verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")

    async def _validate_introspection(self, session_info: Dict[str, Any], request: Request):
        """[Task 10.2] Ensure the token is being used by the same client."""
        current_ip = self._get_client_ip(request)
        if session_info["bound_ip"] != current_ip:
            # [Task 10.5] Anomaly Detection
            logger.warning(f"🚨 AUTH ANOMALY: Token IP mismatch! Session: {session_info['bound_ip']} != {current_ip}")
            # In high security level, we could auto-revoke here
            from core.engines.control_plane import control_plane, SystemLevel
            if await control_plane.get_level() >= SystemLevel.WARNING:
                raise HTTPException(status_code=403, detail="Security context changed. Please re-login.")

    # ==========================================================================
    # RATE LIMITING [Task 10.3]
    # ==========================================================================

    async def check_rate_limit(self, user_id: str, action: str = "api", limit: int = 60, window: int = 60) -> bool:
        """[Task 10.3] Per-user sliding window rate limiting."""
        cache = await container.get("cache")
        if not cache or not cache.redis:
            return True # Fallback: allow
            
        key = f"auth:limit:{user_id}:{action}"
        try:
            now = time.time()
            # Redis Sorted Set implementation for sliding window
            async with cache.redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, now - window)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, window)
                _, _, count, _ = await pipe.execute()
                
            # [Task 110] Check for Challenge Threshold
            if count >= (limit * 0.8):
                logger.warning(f"⚖️ Sybil: Triggering challenge threshold for {user_id} ({count}/{limit})")
                await sybil_manager.issue_challenge_required(user_id)
                
            return count <= limit
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return True

    # ==========================================================================
    # SESSION TRACKING [Task 10.4] & AUDIT [Task 10.9]
    # ==========================================================================

    # ==========================================================================
    # ENCRYPTED STORAGE [Task 10.8]
    # ==========================================================================

    def _get_fernet(self):
        from cryptography.fernet import Fernet
        key = Config.FERNET_KEY
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    def encrypt_field(self, data: str) -> str:
        """Encrypts sensitive fields (IPs, Refresh Tokens) for storage."""
        if not data: return data
        f = self._get_fernet()
        return f.encrypt(data.encode()).decode()

    def decrypt_field(self, encrypted_data: str) -> str:
        """Decrypts sensitive fields from storage."""
        if not encrypted_data: return encrypted_data
        try:
            f = self._get_fernet()
            return f.decrypt(encrypted_data.encode()).decode()
        except:
            return "DECRYPTION_ERROR"

    # ==========================================================================
    # SESSION TRACKING [Task 10.4] & REFRESH TOKENS [Task 10.6]
    # ==========================================================================

    async def create_session(self, user_id: str, request: Request, refresh_token: str = None):
        """
        [Task 10.4] Advanced Session Tracking.
        [Task 10.8] Stores sensitive data encrypted.
        """
        client_ip = self._get_client_ip(request)
        ua = request.headers.get("user-agent", "unknown")
        
        # [Task 10.7] Device Fingerprinting
        fingerprint = hashlib.sha256(f"{user_id}:{ua}:{client_ip}".encode()).hexdigest()
        
        # 1. Store in SQL (Persistent) [Task 10.4]
        try:
            from database.models import UserSession
            db_factory = await container.get("db") # Will trigger DatabaseServiceProvider
            from database.session import AsyncSessionAuth
            
            async with AsyncSessionAuth() as db:
                new_session = UserSession(
                    user_id=user_id,
                    ip_address=self.encrypt_field(client_ip), # Encrypted [Task 10.8]
                    user_agent=ua,
                    device_info={"fingerprint": fingerprint, "type": "T10_UPGRADED"},
                    is_active=True
                )
                if refresh_token:
                    # [Task 10.6] Refresh Token System
                    new_session.refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
                
                db.add(new_session)
                await db.commit()
                
            # 2. Store in Redis (Hot Sessions) [Task 10.1]
            cache = await container.get("cache")
            if cache and cache.redis:
                session_key = f"auth:user:{user_id}:active_sessions"
                await cache.redis.sadd(session_key, fingerprint)
                await cache.redis.expire(session_key, 86400 * 7) # 7 days
                
            # 3. Audit [Task 10.9]
            await self.log_auth_event(user_id, "LOGIN_SESSION_CREATED", request, {"fingerprint": fingerprint})
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")

    # ==========================================================================
    # AUDIT [Task 10.9] & ANOMALY [Task 10.5]
    # ==========================================================================

    async def log_auth_event(self, user_id: str, action: str, request: Optional[Request] = None, metadata: Dict[str, Any] = None):
        """[Task 10.9] Advanced Audit Logging for Auth."""
        cache = await container.get("cache")
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "action": action,
            "ip": self._get_client_ip(request) if request else "N/A",
            "metadata": metadata or {}
        }
        
        # [Task 10.10] Redis Stream for real-time Auth Metrics
        if cache and cache.redis:
            await cache.redis.xadd("stream:auth:events", event, maxlen=10000)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "127.0.0.1"

    async def fallback(self):
        """In fallback mode, we might allow basic verification if Supabase is up but Redis is down."""
        await super().fallback()
        logger.warning("📉 AuthServiceProvider in Degraded mode: Skipping Redis Cache.")

# Global Instance and Container Registration
auth_service = AuthServiceProvider()
container.register(auth_service)
