from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.services.user_service import UserService
from backend.services.payment_service import PaymentService
from backend.utils.security import decode_access_token, credentials_exception
from backend.services.cache_service import cache_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
# Optional OAuth2 scheme for endpoints that may accept anonymous requests
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from a JWT token.
    Checks if the token has been blacklisted.
    """
    if cache_service.is_available():
        if cache_service.get(f"jwt_blacklist:{token}"):
            raise credentials_exception

    token_data = decode_access_token(token)
    user_service = UserService(db)
    user = user_service.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


def get_optional_user(
    token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
):
    """Return a User when a valid token is provided, otherwise return None.
    This allows endpoints (like /chat) to accept anonymous requests while still
    supporting authenticated users when a Bearer token is supplied.
    """
    if not token:
        return None
    try:
        token_data = decode_access_token(token)
    except Exception:
        return None
    user_service = UserService(db)
    return user_service.get_user_by_email(email=token_data.email) or None

async def verify_webhook_signature(request: Request):
    """Dependency to verify the signature of incoming Razorpay webhooks."""
    webhook_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Razorpay-Signature header not found.")

    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(webhook_body, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")
