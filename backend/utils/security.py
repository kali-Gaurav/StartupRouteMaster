from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
import hmac
import hashlib
import logging

from schemas.base import TokenData
from database.config import Config

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. PASSWORD SECURITY (RESTORED)
# ==============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)


# ==============================================================================
# 2. JWT UTILITIES (RESTORED)
# ==============================================================================
SECRET_KEY = Config.JWT_SECRET_KEY or Config.SUPABASE_JWT_SECRET or "a_very_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenData]:
    """Decodes a JWT access token and returns the payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return TokenData(email=email)
    except JWTError:
        raise credentials_exception


# ==============================================================================
# 3. WEBHOOK SECURITY (TASK 30 - ADDED)
# ==============================================================================
# [30.1] Shared Secret for Webhooks
WEBHOOK_SECRET = Config.JWT_SECRET_KEY 

def verify_webhook_signature(payload_bytes: bytes, signature: str) -> bool:
    """[30.2] HMAC-SHA256 Signature Validation."""
    if not signature: return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

async def signature_guard(request: Request):
    """
    Subtask 30.3: Dependency guard for FastAPI routes.
    Expects 'X-RM-Signature' header.
    """
    signature = request.headers.get("X-RM-Signature")
    if not signature:
        logger.warning("Webhook received without signature header.")
        raise HTTPException(status_code=401, detail="Missing signature.")
        
    body = await request.body()
    if not verify_webhook_signature(body, signature):
        logger.error("Invalid webhook signature detected! Potential spoofing attempt.")
        raise HTTPException(status_code=401, detail="Invalid signature.")
        
    return True

def sanitize_string(text: str, length_limit: int = 100) -> str:
    """
    [38.1] Sanitizes user input to prevent XSS/Injection.
    - Strips HTML tags.
    - Removes non-alphanumeric except spaces and commas.
    - Truncates to limit.
    """
    if not text: return ""
    import re
    # 1. Strip HTML tags
    clean = re.sub(r'<.*?>', '', text)
    # 2. Keep only safe characters: A-Z, 0-9, space, comma
    clean = re.sub(r'[^a-zA-Z0-9\s,]', '', clean)
    # 3. Truncate
    return clean[:length_limit].strip()

def mask_result_by_tier(journey: dict, tier: str) -> dict:
    """
    [Industrial Rigor] Physically removes premium fields from basic responses.
    Ensures that metadata like 'guardian_score' or 'ml_confidence' is never leaked.
    """
    tier = (tier or "BASIC").upper()
    if tier == "ELITE":
        return journey
    
    # Define restricted fields for ALL below ELITE
    restricted = ["guardian_score", "ml_confidence", "detailed_risk_breakdown", "active_agent_count"]
    
    if tier == "BASIC":
        # BASIC gets even less
        restricted.extend(["predicted_availability", "social_security_index", "comfort_rank"])
        
    # Recursive masking if needed, but for now just flat pop
    for field in restricted:
        journey.pop(field, None)
        
    return journey
