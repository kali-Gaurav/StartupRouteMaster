import uuid
import logging
from datetime import datetime
from typing import Optional, List

from guardian_ai.models import Mission, MissionStatus, JourneyDetails, RiskLevel, SafetyEvent, LocationMetadata
from guardian_ai.memory_store import guardian_memory

logger = logging.getLogger("mission_manager")

class MissionManager:
    """
    Phase 1: Mission System
    Responsible for the lifecycle of a user's safety journey (Mission).
    """

    async def start_mission(self, user_id: str, journey_data: dict) -> Mission:
        """
        Initializes a new safety mission for a passenger.
        """
        # Close any existing active missions for this user to avoid conflicts
        active_missions = await guardian_memory.get_active_missions_for_user(user_id)
        for old_mission in active_missions:
            await self.complete_mission(old_mission.mission_id)

        mission_id = f"msn_{uuid.uuid4().hex[:12]}"
        
        journey = JourneyDetails(
            pnr=journey_data.get("pnr"),
            train_number=journey_data.get("train_number"),
            source_station=journey_data["source"],
            destination_station=journey_data["destination"],
            departure_time=datetime.fromisoformat(journey_data["departure_time"]),
            arrival_time=datetime.fromisoformat(journey_data["arrival_time"])
        )

        mission = Mission(
            mission_id=mission_id,
            user_id=user_id,
            journey=journey
        )

        logger.info(f"🚀 Mission {mission_id} started for user {user_id}")
        await guardian_memory.save_mission(mission)
        return mission

    async def get_current_mission(self, user_id: str) -> Optional[Mission]:
        """Gets the currently active mission for a user."""
        active_missions = await guardian_memory.get_active_missions_for_user(user_id)
        if active_missions:
            return active_missions[0]  # Assuming 1 active mission per user
        return None

    async def update_location(self, mission_id: str, lat: float, lng: float, station: Optional[str] = None) -> Optional[Mission]:
        """Updates the tracking location of the passenger."""
        mission = await guardian_memory.get_mission(mission_id)
        if not mission:
            return None
            
        mission.location = LocationMetadata(lat=lat, lng=lng, last_known_station=station)
        await guardian_memory.save_mission(mission)
        logger.debug(f"📍 Mission {mission_id} location updated: {station or (lat, lng)}")
        return mission

    async def log_safety_event(self, mission_id: str, category: str, description: str, risk_delta: float) -> Optional[Mission]:
        """
        Logs a safety event (e.g. 'train delayed', 'user reported fear') 
        and adjusts the mission's cumulative risk score.
        """
        mission = await guardian_memory.get_mission(mission_id)
        if not mission:
            return None

        event = SafetyEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            category=category,
            description=description,
            risk_delta=risk_delta
        )
        mission.events.append(event)
        
        # Adjust Risk Score
        mission.risk_score = max(0.0, min(100.0, mission.risk_score + risk_delta))
        
        # Recalculate Risk Level
        if mission.risk_score >= 80:
            mission.risk_level = RiskLevel.CRITICAL
        elif mission.risk_score >= 50:
            mission.risk_level = RiskLevel.HIGH
        elif mission.risk_score >= 20:
            mission.risk_level = RiskLevel.MODERATE
        else:
            mission.risk_level = RiskLevel.LOW
            
        logger.warning(f" Safety Event logged on Mission {mission_id}: {category} | New Risk: {mission.risk_level} ({mission.risk_score})")
        await guardian_memory.save_mission(mission)
        return mission

    async def complete_mission(self, mission_id: str) -> bool:
        """Marks a mission as safely completed."""
        mission = await guardian_memory.get_mission(mission_id)
        if mission:
            mission.status = MissionStatus.COMPLETED
            await guardian_memory.save_mission(mission)
            logger.info(f"✅ Mission {mission_id} completed successfully.")
            return True
        return False

mission_manager = MissionManager()
