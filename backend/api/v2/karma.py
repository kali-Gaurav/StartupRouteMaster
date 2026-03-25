import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User
from api.dependencies import get_current_user

logger = logging.getLogger("karma-api")
router = APIRouter(prefix="/karma", tags=["karma"])

@router.get("/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    """
    [Task 43.E] Fetch Top 20 Karma Leaders globally.
    """
    top_users = db.query(User).filter(User.karma_score > 0).order_by(User.karma_score.desc()).limit(20).all()
    
    return [
        {
            "user_id": u.id[:8] + "...",
            "email_obs": u.email[:3] + "***" if u.email else "Anonymous",
            "score": u.karma_score,
            "tier": "ELITE" if u.karma_score > 5000 else "PRO" if u.karma_score > 1000 else "FREE"
        }
        for u in top_users
    ]

@router.get("/me")
async def get_my_karma(user: User = Depends(get_current_user)):
    """
    Returns current user's karma stats.
    """
    return {
        "score": user.karma_score,
        "referral_code": user.referral_code,
        "conversions": 0 # TODO: Count children in DB
    }
