"""
Simple Delay Service for Railway Intelligence Engine

Phase 4 - Step 1: Basic train delay reporting with event publishing
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from backend.config import Config
from backend.services.event_producer import publish_train_delayed

logger = logging.getLogger(__name__)

class DelayService:
    """Simple delay service with event publishing"""

    def __init__(self):
        self.delays: Dict[str, Dict[str, Any]] = {}  # In-memory storage for demo

    async def report_train_delay(self,
                               train_id: str,
                               delay_minutes: int,
                               station_code: str,
                               scheduled_departure: str,
                               estimated_departure: str,
                               reason: Optional[str] = None) -> Dict[str, Any]:
        """Report a train delay and publish event"""

        # Store delay report (in real system, this would update database/cache)
        delay_key = f"{train_id}_{station_code}_{scheduled_departure}"
        delay_data = {
            "train_id": train_id,
            "delay_minutes": delay_minutes,
            "station_code": station_code,
            "scheduled_departure": scheduled_departure,
            "estimated_departure": estimated_departure,
            "reason": reason,
            "reported_at": datetime.utcnow().isoformat()
        }
        self.delays[delay_key] = delay_data

        # Fire-and-forget: publish delay event
        if Config.KAFKA_ENABLE_EVENTS:
            try:
                success = await publish_train_delayed(
                    train_id=train_id,
                    delay_minutes=delay_minutes,
                    station_code=station_code,
                    scheduled_departure=scheduled_departure,
                    estimated_departure=estimated_departure,
                    reason=reason
                )
                if success:
                    logger.debug(f"Published delay event for train {train_id}")
                else:
                    logger.warning(f"Failed to publish delay event for train {train_id}")
            except Exception as e:
                logger.error(f"Error publishing delay event: {e}")

        logger.info(f"Train delay reported: {train_id} at {station_code}, {delay_minutes} minutes")
        return delay_data

    def get_train_delays(self, train_id: str) -> List[Dict[str, Any]]:
        """Get all delay reports for a train"""
        return [delay for delay in self.delays.values() if delay["train_id"] == train_id]

    def get_station_delays(self, station_code: str) -> List[Dict[str, Any]]:
        """Get all delay reports for a station"""
        return [delay for delay in self.delays.values() if delay["station_code"] == station_code]

# Global instance
delay_service = DelayService()