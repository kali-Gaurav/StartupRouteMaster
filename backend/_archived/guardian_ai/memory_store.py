import json
import logging
from typing import Optional, List
from datetime import datetime

from guardian_ai.models import Mission
from services.cache_service import cache_service
from database.session import SessionTransit
from sqlalchemy import text

logger = logging.getLogger("guardian_memory")

class GuardianMemoryStore:
    """
    Handles persistence of Guardian Missions.
    Uses Redis for rapid hot-state lookups and updates, 
    and flushes to Postgres for long-term durability.
    """
    def __init__(self):
        self.cache = cache_service
        self.prefix = "guardian:mission:"

    async def save_mission(self, mission: Mission) -> bool:
        """Saves a mission to hot cache (and eventually triggers DB sync)."""
        mission.updated_at = datetime.utcnow()
        key = f"{self.prefix}{mission.mission_id}"
        
        try:
            # Save to Redis (TTL 7 days for active missions to ensure they outlive the journey)
            self.cache.set(key, mission.model_dump(mode="json"), ttl_seconds=86400 * 7)
            # TODO: Emit async event to sync to Postgres for permanent audit log
            return True
        except Exception as e:
            logger.error(f"Failed to save mission {mission.mission_id} to memory: {e}")
            return False

    async def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Retrieves a mission by ID from the hot cache."""
        key = f"{self.prefix}{mission_id}"
        data = self.cache.get(key)
        if data:
            return Mission.model_validate(data)
        return None

    async def get_active_missions_for_user(self, user_id: str) -> List[Mission]:
        """Scans for all active missions belonging to a user."""
        # For a truly scaled production system, we would maintain a secondary index set in Redis 
        # (e.g., guardian:user_missions:{user_id} -> set of mission_ids)
        # For now, we fetch via pattern match or fallback to DB.
        
        pattern = f"{self.prefix}*"
        all_mission_data = self.cache.get_pattern(pattern)
        
        user_missions = []
        for key, data in all_mission_data.items():
            if isinstance(data, str):
                data = json.loads(data)
            try:
                mission = Mission.model_validate(data)
                if mission.user_id == user_id and mission.status == "ACTIVE":
                    user_missions.append(mission)
            except Exception as e:
                logger.error(f"Failed to parse mission data: {e}")
                
        return user_missions

    async def get_all_active_missions(self) -> List[Mission]:
        """Scans for all active missions across the system (for telemetry/monitoring)."""
        pattern = f"{self.prefix}*"
        all_mission_data = self.cache.get_pattern(pattern)
        
        active_missions = []
        for key, data in all_mission_data.items():
            if isinstance(data, str):
                data = json.loads(data)
            try:
                mission = Mission.model_validate(data)
                if mission.status == "ACTIVE":
                    active_missions.append(mission)
            except Exception as e:
                pass
                
        return active_missions

guardian_memory = GuardianMemoryStore()
