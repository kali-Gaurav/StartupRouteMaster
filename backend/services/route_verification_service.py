import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import json

from core.route_engine.data_provider import DataProvider
from database.models import Trip, StopTime, Stop, Segment, Station
from core.redis import async_redis_client

logger = logging.getLogger(__name__)

class RouteVerificationService:
    """
    Intelligent service for verifying route information during unlock payment.
    Consolidates Seat Availability (RapidAPI) and Live Status (RappidURL).
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.data_provider = DataProvider()

    async def verify_route_for_unlock(
        self,
        route_id: str,
        travel_date: str,
        train_number: Optional[str] = None,
        from_station_code: Optional[str] = None,
        to_station_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive verification of all route segments.
        Called when user clicks 'Unlock Details'.
        """
        # 1. Extract full route segments
        route_info = await self._extract_route_info(route_id, train_number, from_station_code, to_station_code)
        
        if not route_info["success"]:
            return {"success": False, "error": "Route details not found in cache or DB"}

        segments = route_info.get("segments", [])
        from services.seat_verification import SeatVerificationService
        from services.live_status_service import LiveStatusService
        
        seat_svc = SeatVerificationService()
        live_svc = LiveStatusService()
        
        verification_details = []
        overall_available = True
        warnings = []

        # 2. Verify EVERY segment in the journey
        for seg in segments:
            t_no = seg.get("train_number")
            f_code = seg.get("from_station_code") or seg.get("from_station")
            t_code = seg.get("to_station_code") or seg.get("to_station")
            
            status = {"train_number": t_no, "from": f_code, "to": t_code}

            # A. Seat Check
            try:
                is_avl = await seat_svc.check_segment(
                    train_no=t_no, from_code=f_code, to_code=t_code,
                    date_str=travel_date, class_type=seg.get("class_type", "3A")
                )
                status["seats"] = "AVAILABLE" if is_avl else "WAITLIST"
                if not is_avl: overall_available = False
            except Exception:
                status["seats"] = "ERROR"

            # B. Live Status Check
            try:
                live = live_svc.get_live_status(t_no)
                if live and live.get("success"):
                    status["live"] = live.get("message")
                    if live.get("delay_minutes", 0) > 60:
                        warnings.append(f"Train {t_no} is delayed by {live.get('delay_minutes')}m")
            except Exception:
                status["live"] = "DELAY_UNKNOWN"

            verification_details.append(status)

        return {
            "success": True,
            "overall_available": overall_available,
            "segments": verification_details,
            "warnings": list(set(warnings)),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _extract_route_info(self, route_id, train_number, from_code, to_code) -> Dict:
        # Try Cache First (Modern Flow)
        if route_id.startswith(("rt_", "turbo_")):
            from services.journey_cache import get_journey
            journey = await get_journey(route_id)
            if journey:
                logger.info(f"DEBUG: Cache HIT for {route_id}")
                return {"success": True, "segments": journey.get("legs", [])}
            else:
                logger.warning(f"DEBUG: Cache MISS for {route_id}")

        # Try DB (Legacy/Direct Flow)
        if train_number and from_code and to_code:
            return {
                "success": True, 
                "segments": [{"train_number": train_number, "from_station_code": from_code, "to_station_code": to_code}]
            }
            
        return {"success": False}
