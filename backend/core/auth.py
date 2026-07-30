"""
Authentication Service - JWT-based authentication.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import User

logger = logging.getLogger("auth")

# Security configuration
SECRET_KEY = "your-secret-key-change-in-production"  # Load from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer scheme
security = HTTPBearer()


@dataclass
class TokenData:
    """Token payload data."""
    user_id: str
    email: str
    exp: datetime


@dataclass
class UserResponse:
    """User response data."""
    id: str
    phone: str
    email: Optional[str]
    name: Optional[str]
    created_at: datetime


class AuthService:
    """Authentication service."""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash password."""
        return pwd_context.hash(password)
    
    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token."""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Optional[TokenData]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenData(
                user_id=payload.get("sub"),
                email=payload.get("email"),
                exp=datetime.fromtimestamp(payload.get("exp"))
            )
        except JWTError as e:
            logger.error(f"Token decode error: {e}")
            return None
    
    async def authenticate_user(
        self,
        db: Session,
        phone: str,
        password: str
    ) -> Optional[User]:
        """Authenticate user with phone and password."""
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    async def create_user(
        self,
        db: Session,
        phone: str,
        password: str,
        email: Optional[str] = None,
        name: Optional[str] = None
    ) -> User:
        """Create new user."""
        # Check if user exists
        existing = db.query(User).filter(User.phone == phone).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        
        user = User(
            id=str(datetime.now().timestamp()).replace(".", "")[:12],
            phone=phone,
            hashed_password=self.get_password_hash(password),
            email=email,
            name=name,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user


# Singleton instance
auth_service = AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Usage:
        @router.get("/protected")
        async def protected_endpoint(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        token_data = auth_service.decode_token(token)
        
        if token_data is None:
            raise credentials_exception
        
        user = db.query(User).filter(User.id == token_data.user_id).first()
        if user is None:
            raise credentials_exception
        
        return user
        
    except JWTError:
        raise credentials_exception


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    
    Usage:
        @router.get("/optional-auth")
        async def optional_endpoint(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.phone}"}
            return {"message": "Hello anonymous"}
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def create_test_token(user_id: str = "test-user-123", email: str = "test@example.com") -> str:
    """Create test token for development."""
    return auth_service.create_access_token(user_id, email)