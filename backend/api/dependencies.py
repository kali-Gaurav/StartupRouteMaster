from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session


from database.models import User
from database.session import get_db
from services.user_service import UserService
from services.payment_service import PaymentService
from utils.security import decode_access_token, credentials_exception
from services.cache_service import cache_service

# supabase client used for token validation
from supabase_client import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
# Optional OAuth2 scheme for endpoints that may accept anonymous requests
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Verify the bearer token with Supabase auth and return the corresponding
    local User record (creating a stub if it doesn't exist).  This keeps the
    existing codebase able to reference a SQLAlchemy `User` object while the
    authoritative authentication lives in Supabase.
    """
    # first check local blacklist (redis) if present; old tokens we rejected
    if cache_service.is_available():
        if cache_service.get(f"jwt_blacklist:{token}"):
            raise credentials_exception

    # verify against Supabase; the client method will raise or return error
    try:
        resp = supabase.auth.get_user(token)
    except Exception as e:
        raise credentials_exception
    if resp.get("error") or not resp.get("data"):
        raise credentials_exception
    sb_user = resp["data"]

    user_service = UserService(db)
    # look up by supabase_id first, then email if necessary
    user = None
    if sb_user.get("id"):
        user = user_service.get_user_by_supabase_id(sb_user["id"])
    if not user and sb_user.get("email"):
        user = user_service.get_user_by_email(sb_user["email"])
    # if still missing create a record so that the rest of the service works
    if not user:
        user = user_service.create_user_with_data({
            "email": sb_user.get("email"),
            "supabase_id": sb_user.get("id"),
            "password_hash": "",  # placeholder, auth handled by Supabase
        })
    return user


def get_optional_user(
    token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
):
    """Return a User when a valid Supabase token is provided, otherwise None."""
    if not token:
        return None
    try:
        resp = supabase.auth.get_user(token)
    except Exception:
        return None
    if resp.get("error") or not resp.get("data"):
        return None
    sb_user = resp["data"]
    user_service = UserService(db)
    user = None
    if sb_user.get("id"):
        user = user_service.get_user_by_supabase_id(sb_user["id"])
    if not user and sb_user.get("email"):
        user = user_service.get_user_by_email(sb_user["email"])
    return user

async def verify_webhook_signature(request: Request):
    """Dependency to verify the signature of incoming Razorpay webhooks."""
    webhook_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Razorpay-Signature header not found.")

    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(webhook_body, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")
