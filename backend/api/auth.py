from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/auth", tags=["auth"])

# All authentication is now handled by Supabase.  The backend no longer
# maintains passwords or issues tokens.  Frontend clients should call the
# Supabase JavaScript/Rest API directly for sign‑up, sign‑in, password reset,
# social logins, etc.
#
# This router is retained solely to return a helpful error if legacy clients
# or scripts hit the old endpoints.

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def deprecated(path: str):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Authentication endpoints have been migrated to Supabase. "
               "Please use the Supabase client libraries or direct REST calls."
    )

