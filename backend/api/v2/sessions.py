from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
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
            id=s.id,
            ip_address=s.ip_address or "Unknown",
            user_agent=s.user_agent or "Unknown",
            login_at=s.login_at,
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
