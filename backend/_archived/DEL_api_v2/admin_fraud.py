import logging
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, FraudAlert, IdentityFingerprint
from api.dependencies import require_role
from utils.responses import success_response

logger = logging.getLogger("admin-fraud-api")
router = APIRouter(prefix="/admin/fraud", tags=["admin-fraud"])

@router.get("/alerts", dependencies=[Depends(require_role(["admin"]))])
async def get_active_alerts(db: Session = Depends(get_db)):
    """List high-severity fraud alerts."""
    alerts = db.query(FraudAlert).order_by(FraudAlert.severity.desc(), FraudAlert.timestamp.desc()).limit(50).all()
    data = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "metadata": a.metadata_json,
            "time": a.timestamp
        }
        for a in alerts
    ]
    return success_response(data=data)

@router.post("/ban/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def ban_user(user_id: str, db: Session = Depends(get_db)):
    """Administrative Ban for Fraud."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found.")
    
    user.role = "BANNED"
    db.commit()
    logger.critical(f"ADMIN_USER_BAN | {user_id}")
    return success_response(message=f"User {user_id} is now BANNED.")
