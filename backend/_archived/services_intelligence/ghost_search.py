import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from sqlalchemy.orm import Session
from database.session import SessionTransit
from database.models import Booking
from core.data_utils.structures import Route, RouteSegment, Persona
from services.search_service import SearchService
from services.live_status_service import LiveStatusService
from services.communication.alert_service import AlertService

logger = logging.getLogger(__name__)

class GhostSearchService:
    """
    [Phase B: Ghost Search] Autonomous Re-accommodation Engine.
    Monitors active journeys for disruptions and proactively searches for alternatives.
    """
    
    def __init__(self, db: Session, search_service: SearchService, live_status: LiveStatusService, alert_service: AlertService):
        self.db = db
        self.search_service = search_service
        self.live_status = live_status
        self.alert_service = alert_service
        self._running = False

    async def start_monitoring(self, interval_sec: int = 300):
        """Starts the background monitoring loop."""
        self._running = True
        logger.info(f"👻 [GHOST_SEARCH] Monitoring service started (Interval: {interval_sec}s)")
        while self._running:
            try:
                await self.monitor_active_journeys()
            except Exception as e:
                logger.error(f"Error in GhostSearch loop: {e}", exc_info=True)
            await asyncio.sleep(interval_sec)

    def stop_monitoring(self):
        self._running = False

    async def monitor_active_journeys(self):
        """Checks health of all active journeys."""
        # Fetch active bookings (confirmed and within travel window)
        now = datetime.utcnow()
        active_bookings = self.db.query(Booking).filter(
            Booking.booking_status == "confirmed",
            Booking.travel_date >= now.date()
        ).all()
        
        logger.debug(f"Checking {len(active_bookings)} active bookings for disruptions...")
        
        for booking in active_bookings:
            await self._check_booking_health(booking)

    async def _check_booking_health(self, booking: Booking):
        """Evaluates connection risk for a specific booking."""
        route_data = booking.booking_details
        if not route_data or 'segments' not in route_data:
            return

        segments = route_data['segments']
        for i in range(len(segments) - 1):
            seg_arr = segments[i]
            seg_dep = segments[i+1]
            
            # Check if this connection is at risk
            risk_detected = await self._is_connection_broken(seg_arr, seg_dep)
            if risk_detected:
                logger.warning(f"🚨 [GHOST_SEARCH] Connection break detected for PNR {booking.pnr_number} at {seg_arr['to_station']}")
                await self._perform_ghost_search(booking, i)
                break # Only one re-accommodation needed per journey at a time

    async def _is_connection_broken(self, incoming_seg: Dict, outgoing_seg: Dict) -> bool:
        """Determines if the delay of incoming train exceeds the transfer buffer."""
        train_num = incoming_seg.get('train_number')
        if not train_num: return False
        
        # Fetch live delay
        status = await self.live_status.get_live_status(train_num)
        delay_mins = status.get('delay_minutes', 0)
        
        scheduled_arr = datetime.fromisoformat(incoming_seg['arrival_time'])
        scheduled_dep = datetime.fromisoformat(outgoing_seg['departure_time'])
        
        buffer_mins = (scheduled_dep - scheduled_arr).total_seconds() / 60
        
        # If delay consumes > 85% of buffer or leaves < 10 mins, it's broken
        if delay_mins > (buffer_mins - 10):
            return True
            
        return False

    async def _perform_ghost_search(self, booking: Booking, break_idx: int):
        """Executes 'Ghost Search' to find alternatives from the point of failure."""
        route_data = booking.booking_details
        segments = route_data['segments']
        point_of_failure = segments[break_idx]['to_station']
        destination = segments[-1]['to_station']
        
        logger.info(f"👻 [GHOST_SEARCH] Initiating alternative search from {point_of_failure} to {destination}...")
        
        # Trigger alternative search
        # We use a tighter, speed-focused persona for re-accommodation
        alternatives = await self.search_service.search_routes(
            source=point_of_failure,
            destination=destination,
            travel_date=datetime.utcnow().strftime("%Y-%m-%d"), # Search for today
            budget_category=Persona.EMERGENCY.value, 
            limit=5
        )
        
        journeys = alternatives.get('journeys', [])
        if journeys:
            best_alt = journeys[0]
            # Ensure we have a Route object for the alert
            logger.info(f"✅ [GHOST_SEARCH] Found {len(journeys)} alternatives. Best: {getattr(best_alt, 'journey_id', 'N/A')}")
            await self._alert_user(booking, best_alt)

    async def _alert_user(self, booking: Booking, alternative: Route):
        """Sends a proactive alert to the user with the alternative journey."""
        msg = (
            f"🚨 Connection Alert! Your train to {booking.booking_details['segments'][0]['to_station']} is delayed. "
            f"We've found an alternative: {alternative.segments[0].train_number} departing at "
            f"{alternative.segments[0].departure_time.strftime('%H:%M')}. "
            f"Click here to re-book now!"
        )
        
        await self.alert_service.send_user_alert(
            user_id=booking.user_id,
            message=msg,
            alert_type="REACCOMMODATION",
            metadata={"alternative_route_id": alternative.journey_id, "pnr": booking.pnr_number}
        )

# Factory function
def get_ghost_search_service(db: Session) -> GhostSearchService:
    from services.search_service import SearchService
    from services.live_status_service import LiveStatusService
    from services.communication.alert_service import AlertService
    
    return GhostSearchService(
        db=db,
        search_service=SearchService(db),
        live_status=LiveStatusService(),
        alert_service=AlertService(db)
    )
