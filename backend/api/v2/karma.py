import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User
from api.dependencies import get_current_user

logger = logging.getLogger("karma-api")
router = APIRouter(prefix="/karma", tags=["karma"])

def _serialize_leaderboard_user(u: User):
    user_id = str(getattr(u, "id", ""))[:8] + "..."
    email = getattr(u, "email", None)
    score = int(getattr(u, "karma_score", 0) or 0)

    return {
        "user_id": user_id,
        "email_obs": f"{email[:3]}***" if email else "Anonymous",
        "score": score,
        "tier": "ELITE" if score > 5000 else "PRO" if score > 1000 else "FREE"
    }

@router.get("/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    """
    [Task 43.E] Fetch Top 20 Karma Leaders globally.
    """
    top_users = db.query(User).filter(User.karma_score > 0).order_by(User.karma_score.desc()).limit(20).all()
    
    return [
        _serialize_leaderboard_user(u)
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
