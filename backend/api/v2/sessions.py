from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, cast
from database.session import get_db
from database.models import User, UserSession
from api.dependencies import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["Security"])

class SessionRead(BaseModel):
    id: str
    ip_address: str
    user_agent: str
    login_at: datetime
    is_current: bool

@router.get("/", response_model=List[SessionRead])
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all active login sessions for the current user.
    [Enterprise Requirement: Session Visibility]
    """
    # For now, we return the last 10 sessions. 
    # In a full implementation, we'd filter by 'is_active' or similar.
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id
    ).order_by(UserSession.login_at.desc()).limit(10).all()
    
    # We can't easily identify 'is_current' without tracking the specific 
    # token ID, but we can approximate or leave as False for others.
    return [
        SessionRead(
            id=str(s.id),
            ip_address=str(s.ip_address or "Unknown"),
            user_agent=str(s.user_agent or "Unknown"),
            login_at=cast(datetime, s.login_at),
            is_current=False # Approximation
        ) for s in sessions
    ]

@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a specific session.
    [Enterprise Requirement: Remote Logout]
    """
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session revoked"}

# --- Group 4: Dynamic UI Persistence & State Sharding ---
from services.session_lock_service import session_lock_service

class UIStateUpdate(BaseModel):
    state: dict

@router.post("/state")
async def save_ui_state(
    req: UIStateUpdate,
    current_user: User = Depends(get_current_user)
):
    """Saves the comprehensive UI shard for multi-device handoff."""
    await session_lock_service.persist_ui_state(str(current_user.id), req.state)
    return {"status": "success"}

@router.get("/state")
async def get_ui_state(
    current_user: User = Depends(get_current_user)
):
    """Restores the last known UI shard for sub-second hydration."""
    state = await session_lock_service.restore_ui_state(str(current_user.id))
    return {"status": "success", "state": state}

@router.post("/lock/{route_id}")
async def lock_route(
    route_id: str,
    current_user: User = Depends(get_current_user)
):
    """Acquires a temporary lock on a route to prevent booking conflicts."""
    success = await session_lock_service.acquire_route_lock(str(current_user.id), route_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Route is currently held by another session or undergoing verification."
        )
    return {"status": "success", "message": "Route locked for 10 minutes."}

@router.delete("/lock/{route_id}")
async def unlock_route(
    route_id: str,
    current_user: User = Depends(get_current_user)
):
    """Manually releases a held route lock."""
    await session_lock_service.release_route_lock(route_id)
    return {"status": "success"}
