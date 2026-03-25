import logging
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserAlert, NotificationToken, NotificationPreference
from api.dependencies import get_current_user

logger = logging.getLogger("notifications-api")
router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/history")
async def get_notification_history(
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    [Task 46.6] Returns last 30 alerts for the current user.
    """
    alerts = db.query(UserAlert).filter(
        UserAlert.user_id == user.id
    ).order_by(UserAlert.timestamp.desc()).limit(30).all()
    
    return [
        {
            "id": a.id,
            "title": a.title,
            "body": a.body,
            "type": a.alert_type,
            "is_read": a.is_read,
            "time": a.timestamp
        }
        for a in alerts
    ]

@router.post("/register-token")
async def register_fcm_token(
    user: User = Depends(get_current_user),
    channel: str = Body(..., embed=True),
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    [Task 46.1] Save an FCM (Web Push) or Telegram ID.
    """
    exist = db.query(NotificationToken).filter(
        NotificationToken.user_id == user.id,
        NotificationToken.token == token
    ).first()
    
    if not exist:
        nt = NotificationToken(
            user_id=user.id,
            channel=channel,
            token=token
        )
        db.add(nt)
        db.commit()
        return {"status": "REGISTERED", "id": nt.id}
    
    return {"status": "EXISTS"}

@router.patch("/read/{alert_id}")
async def mark_as_read(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark alert as read to clear frontend badges.
    """
    alert = db.query(UserAlert).filter(
        UserAlert.id == alert_id,
        UserAlert.user_id == user.id
    ).first()
    
    if not alert: raise HTTPException(status_code=404)
    
    alert.is_read = True
    db.commit()
    return {"status": "READ"}
