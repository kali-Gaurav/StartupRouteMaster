import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from database.models import SOSEvent, SOSTelemetry, EmergencyContact, User, UserHeartbeat
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("routemaster.sos")

class SOSService:
    def __init__(self, db: Session):
        self.db = db

    async def trigger_sos(self, user_id: str, lat: float, lng: float, 
                         category: str = "MANUAL_TRIGGER", trip_data: Optional[Dict] = None) -> str:
        """
        Subtask 20.1: Immediate SOS Trigger.
        Creates event, logs initial telemetry, and alerts contacts.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # 1. Create SOSEvent
        event = SOSEvent(
            user_id=user_id,
            status="ACTIVE",
            priority="HIGH",
            category=category,
            lat=lat,
            lng=lng,
            name=user.full_name,
            phone=user.phone_number,
            email=user.email,
            trip_data=trip_data,
            triggered_at=datetime.utcnow()
        )
        self.db.add(event)
        self.db.flush() # Get event ID

        # 2. Log First Telemetry
        telemetry = SOSTelemetry(
            event_id=event.id,
            lat=lat,
            lng=lng,
            timestamp=datetime.utcnow()
        )
        self.db.add(telemetry)

        # 3. Alert Contacts (Mock for now, will link to NotifyService)
        contacts = self.db.query(EmergencyContact).filter(EmergencyContact.user_id == user_id).all()
        for contact in contacts:
            logger.warning(f"🚨 ALERT: SOS Triggered for {user.full_name}. Notifying {contact.name} at {contact.phone}")
            # TODO: await notify_service.send_sos_alert(contact, event)

        self.db.commit()
        return event.id

    async def update_heartbeat(self, user_id: str, journey_id: str, 
                               station_code: str, next_eta: datetime) -> None:
        """
        [Point 20.2] Safe-Haven Heartbeat.
        Resets the 'Dead-Man's Switch' for a transfer.
        """
        hb = self.db.query(UserHeartbeat).filter(
            UserHeartbeat.user_id == user_id,
            UserHeartbeat.journey_id == journey_id
        ).first()

        if not hb:
            hb = UserHeartbeat(
                user_id=user_id,
                journey_id=journey_id,
                status="ON_TRACK"
            )
            self.db.add(hb)

        hb.last_station_code = station_code
        # Safety Buffer: 30 mins after expected arrival
        hb.next_check_in_at = next_eta + timedelta(minutes=30)
        hb.status = "ON_TRACK"
        self.db.commit()
        
        logger.info(f"💓 Heartbeat Updated: {user_id} at {station_code}. Next check-in: {hb.next_check_in_at}")

    async def check_overdue_heartbeats(self):
        """
        Background Monitor: Trigger SOS for missed check-ins.
        """
        now = datetime.utcnow()
        overdue = self.db.query(UserHeartbeat).filter(
            UserHeartbeat.status == "ON_TRACK",
            UserHeartbeat.next_check_in_at < now
        ).all()

        for hb in overdue:
            logger.error(f"⚠️ MISSED HEARTBEAT: User {hb.user_id} overdue at {hb.last_station_code}!")
            hb.status = "MISSED_CHECKIN"
            self.db.commit()
            
            # Auto-Trigger SOS for Critical High-Risk Hubs
            await self.trigger_sos(
                user_id=str(hb.user_id),
                lat=hb.lat or 0.0,
                lng=hb.lng or 0.0,
                category="MISSED_HEARTBEAT_AUTO",
                trip_data={"journey_id": hb.journey_id}
            )

    async def resolve_sos(self, event_id: str, resolution_notes: str):
        event = self.db.query(SOSEvent).filter(SOSEvent.id == event_id).first()
        if event:
            event.status = "RESOLVED"
            event.resolved_at = datetime.utcnow()
            event.extra = resolution_notes
            self.db.commit()
            logger.info(f"✅ SOS {event_id} marked as RESOLVED.")
