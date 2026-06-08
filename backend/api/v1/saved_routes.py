"""
RouteMaster — Saved Routes API
================================
POST   /api/v1/users/saved-routes        save a route
GET    /api/v1/users/saved-routes        list saved routes
DELETE /api/v1/users/saved-routes/{id}   delete one
DELETE /api/v1/users/saved-routes        clear all

Table auto-created on first use.
Auth: Bearer token (Firebase-synced JWT via /api/v1/auth/firebase-sync).
Falls back to anonymous user_id from request body if no token.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("routemaster.v1.saved_routes")
router = APIRouter(prefix="/users/saved-routes", tags=["saved-routes"])
bearer = HTTPBearer(auto_error=False)

# In-memory fallback when DB is unavailable
_store: dict[str, list] = {}  # user_id → [route, ...]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_id(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if not credentials:
        return None
    try:
        from api.v1.auth import _decode_token
        payload = _decode_token(credentials.credentials)
        return payload.get("sub") if payload else None
    except Exception:
        return None


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


def _ensure_table():
    from sqlalchemy import text
    try:
        s = _get_session()
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS user_saved_routes (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                from_code  TEXT NOT NULL,
                to_code    TEXT NOT NULL,
                from_name  TEXT DEFAULT '',
                to_name    TEXT DEFAULT '',
                route_data JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        s.execute(text("CREATE INDEX IF NOT EXISTS idx_saved_user ON user_saved_routes(user_id)"))
        s.commit()
        s.close()
    except Exception:
        pass


# ── Schema ────────────────────────────────────────────────────────────────────

class SaveRouteRequest(BaseModel):
    from_code: str
    to_code: str
    from_name: Optional[str] = ""
    to_name: Optional[str] = ""
    route_data: Optional[dict] = None   # full journey object
    user_id: Optional[str] = None       # fallback if no JWT


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def save_route(
    body: SaveRouteRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Save a route to the user's bookmarks."""
    _ensure_table()
    user_id = _get_user_id(credentials) or body.user_id or "anonymous"
    route_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "id": route_id,
        "user_id": user_id,
        "from_code": body.from_code.upper(),
        "to_code": body.to_code.upper(),
        "from_name": body.from_name or body.from_code,
        "to_name": body.to_name or body.to_code,
        "route_data": body.route_data,
        "created_at": now,
    }

    # In-memory
    _store.setdefault(user_id, []).append(record)

    # DB persist
    try:
        from sqlalchemy import text
        s = _get_session()
        s.execute(text("""
            INSERT INTO user_saved_routes
                (id, user_id, from_code, to_code, from_name, to_name, route_data)
            VALUES (:id, :uid, :fc, :tc, :fn, :tn, :rd)
        """), {
            "id": route_id, "uid": user_id,
            "fc": body.from_code.upper(), "tc": body.to_code.upper(),
            "fn": body.from_name or body.from_code,
            "tn": body.to_name or body.to_code,
            "rd": json.dumps(body.route_data) if body.route_data else None,
        })
        s.commit()
        s.close()
    except Exception:
        pass  # In-memory is enough

    return {"id": route_id, "saved": True, "message": f"Route {body.from_code}→{body.to_code} saved."}


@router.get("")
async def list_saved_routes(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """List all saved routes for the current user."""
    user_id = _get_user_id(credentials)
    if not user_id:
        return {"routes": [], "count": 0, "message": "Not authenticated"}

    routes = []

    # Try DB first
    try:
        from sqlalchemy import text
        s = _get_session()
        rows = s.execute(text("""
            SELECT id, from_code, to_code, from_name, to_name, route_data, created_at
            FROM user_saved_routes
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT 50
        """), {"uid": user_id}).fetchall()
        s.close()
        for row in rows:
            rd = None
            try:
                rd = json.loads(row[5]) if isinstance(row[5], str) else row[5]
            except Exception:
                pass
            routes.append({
                "id": row[0],
                "from_code": row[1], "to_code": row[2],
                "from_name": row[3], "to_name": row[4],
                "route_data": rd,
                "created_at": str(row[6]),
            })
    except Exception:
        # Fall back to in-memory
        routes = _store.get(user_id, [])

    return {"routes": routes, "count": len(routes)}


@router.delete("/{route_id}")
async def delete_saved_route(
    route_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Delete a specific saved route."""
    user_id = _get_user_id(credentials)

    # In-memory
    if user_id and user_id in _store:
        _store[user_id] = [r for r in _store[user_id] if r["id"] != route_id]

    # DB
    try:
        from sqlalchemy import text
        s = _get_session()
        clause = "WHERE id = :rid" + (" AND user_id = :uid" if user_id else "")
        params = {"rid": route_id}
        if user_id:
            params["uid"] = user_id
        s.execute(text(f"DELETE FROM user_saved_routes {clause}"), params)
        s.commit()
        s.close()
    except Exception:
        pass

    return {"deleted": True, "id": route_id}


@router.delete("")
async def clear_all_saved(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
):
    """Clear all saved routes for the user."""
    user_id = _get_user_id(credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if user_id in _store:
        del _store[user_id]

    try:
        from sqlalchemy import text
        s = _get_session()
        s.execute(text("DELETE FROM user_saved_routes WHERE user_id = :uid"), {"uid": user_id})
        s.commit()
        s.close()
    except Exception:
        pass

    return {"cleared": True}
