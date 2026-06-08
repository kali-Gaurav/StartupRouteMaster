import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from guardian_ai.safety_engine import safety_engine
from guardian_ai.mission_manager import mission_manager
from guardian_ai.models import Mission
from api.dependencies import get_current_user

logger = logging.getLogger("api.guardian")

router = APIRouter(prefix="/guardian", tags=["Guardian AI"])

class MessagePayload(BaseModel):
    message: str

class LocationPayload(BaseModel):
    lat: float
    lng: float
    station: Optional[str] = None

class MissionStartPayload(BaseModel):
    pnr: Optional[str] = None
    train_number: Optional[str] = None
    source: str
    destination: str
    departure_time: str
    arrival_time: str

@router.post("/mission/start")
async def start_mission(payload: MissionStartPayload, user=Depends(get_current_user)) -> Mission:
    """Initializes a new safety mission for the passenger."""
    mission = await mission_manager.start_mission(user.id, payload.model_dump())
    return mission

@router.post("/message")
async def send_message(payload: MessagePayload, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Processes a user message through the Safety Intelligence Engine."""
    mission = await safety_engine.process_user_message(user.id, payload.message)
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission found for this user.")
    return {"status": "success", "mission_id": mission.mission_id, "risk_level": mission.risk_level}

@router.post("/location")
async def update_location(payload: LocationPayload, user=Depends(get_current_user)) -> Dict[str, Any]:
    """Updates the live location for the active mission."""
    mission = await mission_manager.get_current_mission(user.id)
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission found.")
        
    await mission_manager.update_location(mission.mission_id, payload.lat, payload.lng, payload.station)
    return {"status": "success"}

@router.get("/mission/status")
async def get_mission_status(user=Depends(get_current_user)) -> Mission:
    """Returns the current active mission state."""
    mission = await mission_manager.get_current_mission(user.id)
    if not mission:
        raise HTTPException(status_code=404, detail="No active mission found.")
    return mission
