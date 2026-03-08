from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from database.session import get_db, SessionLocal
from database.models import AdminDashboardSession
from database.config import Config
from pydantic import BaseModel
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta
import jwt
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str

def create_admin_token(username: str):
    expire = datetime.utcnow() + timedelta(hours=8) # Admin sessions last 8h
    payload = {
        "sub": username,
        "admin": True,
        "exp": expire,
        "jti": str(uuid.uuid4())
    }
    token = jwt.encode(payload, Config.SUPABASE_JWT_SECRET or "admin_secret_fallback", algorithm="HS256")
    return token, expire

@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(payload: AdminLoginRequest, request: Request):
    """
    Secure Admin Login with [32.2] Brute-Force Protection.
    """
    from services.cache_service import cache_service
    client_ip = request.client.host
    
    # 1. Check if IP is blocked
    if cache_service.is_ip_blocked(client_ip):
        logger.error(f"BLOCKED: Brute-force attempt from {client_ip}")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 5 minutes.")

    # 2. Credential Check
    is_valid = True
    if payload.username != Config.ADMIN_DASHBOARD_USERNAME:
        is_valid = False
    elif not pbkdf2_sha256.verify(payload.password, Config.ADMIN_DASHBOARD_PASSWORD_HASH):
        is_valid = False

    if not is_valid:
        # Record failure
        fails = cache_service.record_failed_login(client_ip)
        logger.warning(f"Failed admin login ({fails}/10) from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success - Create session
    token, expire = create_admin_token(payload.username)
    
    db = SessionLocal()
    try:
        session = AdminDashboardSession(
            admin_username=payload.username,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=expire
        )
        db.add(session)
        db.commit()
    finally:
        db.close()

    logger.info(f"Admin logged in: {payload.username} from {request.client.host}")
    return {
        "access_token": token,
        "expires_at": expire.isoformat()
    }

async def get_admin_access(authorization: str = Header(...)):
    """
    Dependency to ensure only authorized admins can access analytics.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, Config.SUPABASE_JWT_SECRET or "admin_secret_fallback", algorithms=["HS256"])
        if not payload.get("admin"):
            raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
