from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database.models import User
from database.session import get_db, get_async_auth_db
from database.config import Config
from services.user_service import UserService
from services.payment_service import PaymentService
from core.auth import supabase
from core.auth.permissions import Permissions
import logging

# Task: Phased Microservice Migration
# Import from the new shared microservice layer to ensure single source of truth
import sys
from pathlib import Path
shared_path = str(Path(__file__).resolve().parent.parent)
if shared_path not in sys.path:
    sys.path.append(shared_path)

from microservices.shared.auth import SharedAuthManager

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_async_auth_db)
) -> User:
    """
    [Task 10 Upgrade] Unified IoC-managed Authentication.
    Uses AuthServiceProvider (v2.0.0) with Redis Caching and Introspection.
    """
    # 1. Bypass check for development
    if Config.ENVIRONMENT == "development" and request.headers.get("X-Dev-Bypass") == "TRUE":
        return User(id="dev-admin", email="dev@routemaster.io", role="admin", is_verified=True)

    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    # 2. Get Auth Provider from IoC Container [Task 8 & 10]
    from core.container import container
    auth_service = await container.get("auth")
    
    # [Task 10.2] Verify with Redis Cache + Introspection + Supabase
    user_data = await auth_service.verify_token(token, request)
    
    # 3. Sync with local Database [Task 10.4]
    from microservices.shared.auth import SharedAuthManager
    from services.multi_layer_cache import multi_layer_cache
    
    # We still use SharedAuthManager for DB Operations (Porting to IoC slowly)
    auth_manager = SharedAuthManager(db, multi_layer_cache.redis)
    user = auth_manager.sync_user(user_data)
    
    # 4. [Task 10.3] Per-User Rate Limiting
    if not await auth_service.check_rate_limit(user.id, limit=100, window=60):
        # [Task 10.9] Audit rate limit breach
        await auth_service.log_auth_event(user.id, "RATE_LIMIT_EXCEEDED", request)
        raise HTTPException(status_code=429, detail="Too many requests for your account.")

    # 5. [Task 10.4] Track Activity
    auth_manager.track_session(user.id, request)
    return user

def require_role(allowed_roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)):
        Permissions.has_any_role(allowed_roles)(user)
        return user
    return role_checker

async def get_optional_user(request: Request, token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_async_auth_db)):
    if not token: return None
    try:
        from core.container import container
        auth_service = await container.get("auth")
        user_data = await auth_service.verify_token(token, request)
        
        from microservices.shared.auth import SharedAuthManager
        from services.multi_layer_cache import multi_layer_cache
        auth_manager = SharedAuthManager(db, multi_layer_cache.redis)
        return auth_manager.sync_user(user_data)
    except: return None

async def verify_webhook_signature(request: Request):
    webhook_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature: raise HTTPException(status_code=400, detail="X-Razorpay-Signature header not found.")
    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(webhook_body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
