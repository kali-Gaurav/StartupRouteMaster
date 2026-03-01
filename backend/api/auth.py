from fastapi import APIRouter, HTTPException, status, Request
import logging
from utils.limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# All authentication is now handled by Supabase.  The backend no longer
# maintains passwords or issues tokens.  Frontend clients should call the
# Supabase JavaScript/Rest API directly for sign‑up, sign‑in, password reset,
# social logins, etc.
#
# This router is retained solely to return a helpful error if legacy clients
# or scripts hit the old endpoints.

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@limiter.limit("10/minute")
async def deprecated(request: Request, path: str):
    logger.warning(f"Deprecated auth endpoint hit: {request.method} /api/auth/{path} from {request.client.host if request.client else 'unknown'}")
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Authentication endpoints have been migrated to Supabase. "
               "Please use the Supabase client libraries or direct REST calls."
    )

