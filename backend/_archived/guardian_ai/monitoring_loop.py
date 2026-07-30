import asyncio
import logging
from datetime import datetime

from guardian_ai.mission_manager import mission_manager
from guardian_ai.memory_store import guardian_memory
from guardian_ai.safety_engine import safety_engine
from guardian_ai.action_executor import action_executor
from guardian_ai.models import MissionStatus

logger = logging.getLogger("monitoring_loop")

class AutonomousMonitoringLoop:
    """
    Phase 5: Monitoring Loop
    A continuous background process that evaluates active missions independently 
    of user interactions. This is the heart of the "Autonomous Guardian".
    """
    
    def __init__(self):
        self.is_running = False
        self._task = None

    async def start(self):
        """Starts the autonomous monitoring loop."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("🛡️ Guardian AI Autonomous Monitoring Loop STARTED")

    async def stop(self):
        """Stops the monitoring loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
        logger.info("🛡️ Guardian AI Autonomous Monitoring Loop STOPPED")

    async def _loop(self):
        """The core tick loop."""
        while self.is_running:
            try:
                await self._process_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Guardian Loop tick: {e}")
                
            # Tick every 30 seconds (configurable)
            await asyncio.sleep(30)

    async def _process_tick(self):
        """
        One cycle of the Guardian AI.
        Iterates over all active missions, checks for timeout/inactivity anomalies,
        and triggers safety engines.
        """
        # Note: In a heavily distributed system, we would grab a lock or process 
        # a partitioned subset of missions.
        # For MVP, we'll scan pattern keys.
        pattern = f"{guardian_memory.prefix}*"
        all_mission_data = guardian_memory.cache.get_pattern(pattern)
        
        active_missions = []
        for key, data in all_mission_data.items():
            try:
                # Cache might return raw string or parsed dict depending on implementation
                import json
                from guardian_ai.models import Mission
                if isinstance(data, str):
                    data = json.loads(data)
                mission = Mission.model_validate(data)
                if mission.status == MissionStatus.ACTIVE:
                    active_missions.append(mission)
            except Exception:
                continue

        if not active_missions:
            return

        logger.debug(f"Tick: Monitoring {len(active_missions)} active missions.")

        now = datetime.utcnow()
        for mission in active_missions:
            # 1. Check for inactivity timeout
            time_since_last_update = (now - mission.updated_at).total_seconds()
            
            # If no activity for 2 hours (7200 seconds), escalate risk slightly
            # (In production, this timeout varies based on day/night and location)
            if time_since_last_update > 7200:
                logger.info(f"Mission {mission.mission_id} inactive for >2 hours. Logging anomaly.")
                mission = await mission_manager.log_safety_event(
                    mission_id=mission.mission_id,
                    category="Inactivity Anomaly",
                    description="User has not interacted or updated location for 2 hours.",
                    risk_delta=10.0
                )
            
            # 2. Evaluate mission state
            if mission:
                directives = await safety_engine.evaluate_mission_state(mission)
                if directives:
                    await action_executor.execute_directives(mission, directives)

guardian_loop = AutonomousMonitoringLoop()
