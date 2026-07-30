import logging
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserAlert, NotificationToken, NotificationPreference
from api.dependencies import get_current_user
from utils.responses import success_response, v3_response

logger = logging.getLogger("notifications-api")
router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/history")
async def get_notification_history(
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Returns last 30 alerts for the current user."""
    alerts = db.query(UserAlert).filter(
        UserAlert.user_id == user.id
    ).order_by(UserAlert.timestamp.desc()).limit(30).all()
    
    data = [
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
    logger.info(f"NOTIFICATION_HISTORY_FETCHED | {user.id} | count={len(data)}")
    return v3_response(data=data)

@router.post("/register-token")
async def register_fcm_token(
    user: User = Depends(get_current_user),
    channel: str = Body(..., embed=True),
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Save an FCM (Web Push) or Telegram ID."""
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
        logger.info(f"NOTIFICATION_TOKEN_REGISTERED | {user.id} | {channel}")
        return success_response(message="Token registered", data={"id": nt.id})
    
    logger.info(f"NOTIFICATION_TOKEN_EXISTS | {user.id} | {channel}")
    return success_response(message="Token already exists")

@router.patch("/read/{alert_id}")
async def mark_as_read(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark alert as read to clear frontend badges."""
    alert = db.query(UserAlert).filter(
        UserAlert.id == alert_id,
        UserAlert.user_id == user.id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_read = True
    db.commit()
    logger.info(f"NOTIFICATION_READ | {user.id} | {alert_id}")
    return success_response(message="Marked as read")
