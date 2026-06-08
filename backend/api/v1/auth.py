"""
RouteMaster v1 Auth API
========================
Clean email/password authentication. No Firebase. No microservices.
Uses bcrypt for password hashing, JWT for tokens.

POST /api/v1/auth/register  — create account
POST /api/v1/auth/login     — get JWT token
GET  /api/v1/auth/me        — get current user
POST /api/v1/auth/logout    — revoke session (client-side)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("routemaster.v1.auth")
router = APIRouter(prefix="/auth", tags=["auth-v1"])
bearer_scheme = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "routemaster-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30


# ── JWT helpers ──────────────────────────────────────────────────────────────

def _create_token(user_id: str, email: str) -> str:
    from jose import jwt
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> Optional[dict]:
    try:
        from jose import jwt, JWTError
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


def _hash_password(password: str) -> str:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return ctx.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.verify(plain, hashed)
    except Exception:
        return False


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_session():
    try:
        from database.infrastructure.session import SessionUser
        return SessionUser()
    except Exception:
        try:
            from database.session import SessionLocal
            return SessionLocal()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")


def _find_user_by_email(email: str):
    from sqlalchemy import text
    session = _get_session()
    try:
        row = session.execute(
            text("SELECT id, email, password_hash, full_name, role, created_at FROM users WHERE email = :email LIMIT 1"),
            {"email": email.lower()},
        ).fetchone()
        return dict(row._mapping) if row else None
    except Exception as e:
        logger.error(f"DB user lookup failed: {e}")
        return None
    finally:
        session.close()


def _create_user(email: str, password: str, full_name: str = "") -> dict:
    from sqlalchemy import text
    session = _get_session()
    try:
        user_id = str(uuid.uuid4())
        hashed = _hash_password(password)
        session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, full_name, role, created_at, is_verified)
                VALUES (:id, :email, :hash, :name, 'user', NOW(), false)
            """),
            {"id": user_id, "email": email.lower(), "hash": hashed, "name": full_name},
        )
        session.commit()
        return {"id": user_id, "email": email, "full_name": full_name, "role": "user"}
    except Exception as e:
        session.rollback()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        raise HTTPException(status_code=500, detail=f"Could not create account: {e}")
    finally:
        session.close()


# ── Dependency: get current user from JWT ────────────────────────────────────

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    payload = _decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")
    return payload


def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    if not credentials:
        return None
    payload = _decode_token(credentials.credentials)
    return payload


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = ""

    class Config:
        str_strip_whitespace = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest):
    """Create a new account."""
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing = _find_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = _create_user(body.email, body.password, body.full_name or "")
    token = _create_token(user["id"], user["email"])

    return AuthResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user.get("role", "user"),
        },
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """Authenticate with email + password. Returns JWT."""
    user = _find_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not _verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = _create_token(user["id"], user["email"])
    return AuthResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user.get("role", "user"),
        },
    )


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return current logged-in user info."""
    user = _find_user_by_email(current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "role": user.get("role", "user"),
    }


@router.post("/logout")
async def logout():
    """Client-side logout (JWT is stateless — just tell client to discard token)."""
    return {"message": "Logged out successfully."}


@router.post("/firebase-sync")
async def firebase_sync(body: dict):
    """
    Bridge endpoint for Firebase auth users.
    Accepts a Firebase ID token payload, upserts the user in our DB,
    and returns a backend JWT + user profile.

    Frontend sends this after Firebase login to sync user with backend.
    Body: { firebase_uid, email, display_name, photo_url }
    """
    uid = body.get("firebase_uid", "")
    email = body.get("email", "")
    display_name = body.get("display_name", "")
    photo_url = body.get("photo_url", "")

    if not uid or not email:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="firebase_uid and email are required.")

    # Upsert user in our DB
    from sqlalchemy import text
    session = _get_session()
    try:
        existing = session.execute(
            text("SELECT id, email, full_name, role FROM users WHERE email = :email LIMIT 1"),
            {"email": email.lower()},
        ).fetchone()

        if existing:
            user_id = str(existing[0])
            role = existing[3] or "user"
        else:
            import uuid as _uuid
            user_id = str(_uuid.uuid4())
            role = "user"
            session.execute(
                text("""
                    INSERT INTO users (id, email, password_hash, full_name, role, is_verified, created_at)
                    VALUES (:id, :email, :hash, :name, 'user', true, NOW())
                    ON CONFLICT (email) DO NOTHING
                """),
                {"id": user_id, "email": email.lower(), "hash": "firebase", "name": display_name},
            )
            session.commit()

        token = _create_token(user_id, email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "full_name": display_name,
                "photo_url": photo_url,
                "role": role,
            },
        }
    except Exception as e:
        session.rollback()
        # Return a token even if DB fails — Firebase handles auth
        token = _create_token(uid, email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": uid, "email": email, "full_name": display_name, "role": "user"},
        }
    finally:
        session.close()
