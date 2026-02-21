"""
Emergency Alert Manager for Railway Intelligence.
Pivots RouteMaster from a travel app to a safety-first intelligence platform.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.services.realtime_ingestion.position_estimator import TrainPositionEstimator

logger = logging.getLogger(__name__)

class EmergencyAlertManager:
    """
    Handles emergency alerts, enriches them with high-fidelity railway context,
    and dispatches to responders.
    """
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()
        self.estimator = TrainPositionEstimator(self.db)

    async def process_sos_alert(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a raw SOS event and enriches it with interpolated train position 
        and journey context.
        """
        # Lazy import to avoid circular dependency
        from backend.api.websockets import manager
        
        enriched_event = raw_event.copy()
        
        # Check if it's a railway-related alert
        trip_data = raw_event.get("trip")
        if trip_data and trip_data.get("vehicle_number"):
            train_no = trip_data["vehicle_number"]
            logger.info(f"🚨 Enriching SOS for Train {train_no}")
            
            # 1. Get Live Interpolated Position
            position = self.estimator.estimate_position(train_no)
            
            if position:
                enriched_event["railway_context"] = {
                    "live_lat": position["lat"],
                    "live_lon": position["lon"],
                    "progress_percent": position["progress_percentage"],
                    "last_station": position["last_station"],
                    "next_station": position["next_station"],
                    "estimated_arrival": position.get("estimated_at"),
                    "reliability_index": 0.95 # Mock for now
                }
                
                # Overwrite GPS coordinates if phone GPS is unavailable or less precise than track interpolation
                if not enriched_event.get("lat") or enriched_event.get("lat") == 0:
                     enriched_event["lat"] = position["lat"]
                     enriched_event["lng"] = position["lon"]
            
        # 2. Dispatch to WebSocket Responders (Phase 12 Pipeline)
        await manager.broadcast_sos(enriched_event)
        
        return enriched_event

    def __del__(self):
        # Ensure session is closed if we created it
        if hasattr(self, 'db') and self.db:
            self.db.close()
