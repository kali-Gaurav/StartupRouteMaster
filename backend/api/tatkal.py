from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from pydantic import BaseModel

from database import get_db
from database.models import User
from api.dependencies import get_current_user
from services.tatkal_scheduler_service import tatkal_scheduler

router = APIRouter(prefix="/tatkal", tags=["tatkal"])
logger = logging.getLogger(__name__)

class ForceStartRequest(BaseModel):
    booking_id: str
    is_ac: bool = False

@router.post("/force_start")
async def force_start_tatkal(
    request: ForceStartRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Task 30.9: One-click Tatkal "Force Start".
    Bypasses the clock and immediately executes the preflight and login sequence.
    """
    # In production, ensure only admins or the booking owner can trigger this
    await tatkal_scheduler.sync_ntp_time()
    result = await tatkal_scheduler.execute_tatkal_sequence(
        booking_id=request.booking_id,
        user_id=str(current_user.id),
        is_ac=request.is_ac,
        is_force_start=True
    )
    
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result["message"])
        
    return result

@router.get("/probability")
async def get_success_probability(
    route_popularity: int = Query(..., ge=1, le=10, description="1 to 10 scale of route demand"),
    ping_ms: int = Query(..., ge=1, description="User's internet latency in ms"),
    previous_attempts: int = Query(0, description="Number of times booked before (cache warming)"),
    current_user: User = Depends(get_current_user)
):
    """
    Task 30.10: Success probability calculator.
    Allows frontend to show "Tatkal Mode" warnings based on the score.
    """
    prob = tatkal_scheduler.calculate_success_probability(route_popularity, ping_ms, previous_attempts)
    
    # Task 30.8: Suggest "Tatkal Mode" UI if probability is low
    suggest_tatkal_mode = prob < 60.0
    
    return {
        "success": True, 
        "probability_percentage": round(prob, 2),
        "suggest_tatkal_mode_ui": suggest_tatkal_mode
    }
