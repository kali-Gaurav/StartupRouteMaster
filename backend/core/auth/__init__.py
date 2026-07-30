from .supabase_client import supabase, get_supabase_client

# Re-export JWT auth helpers from parent module to preserve backward compatibility
# This fixes the package/module collision where routers expect:
#   from core.auth import get_current_user
try:
    import sys
    import importlib.util
    spec = importlib.util.spec_from_file_location("core_auth_module", "../auth.py")
    auth_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_module)

    get_current_user = auth_module.get_current_user
    get_current_user_optional = auth_module.get_current_user_optional
    AuthService = auth_module.AuthService
    auth_service = auth_module.auth_service
except (ImportError, AttributeError):
    # Fallback: define minimal versions if module import fails
    from fastapi import HTTPException, status, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from typing import Optional
    from database.session import get_db
    from database.models import User

    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        db = Depends(get_db)
    ) -> User:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
        db = Depends(get_db)
    ) -> Optional[User]:
        return None

__all__ = [
    "supabase",
    "get_supabase_client",
    "get_current_user",
    "get_current_user_optional",
    "AuthService",
    "auth_service"
]
