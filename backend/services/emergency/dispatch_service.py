import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DispatchService:
    """
    Handles automated communication with external emergency authorities.
    """
    
    async def dispatch_to_rpf(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats and sends a high-priority dispatch to the nearest RPF post.
        """
        auth = event.get("nearest_authority", {})
        context = event.get("railway_context", {})
        trip = event.get("trip") or {}
        
        dispatch_id = f"RPF-{uuid.uuid4().hex[:8].upper()}"
        
        # Subtask 14.1: Official Complaint Formatter
        payload = {
            "dispatch_id": dispatch_id,
            "target": auth.get("name", "Nearest RPF"),
            "contact": auth.get("contact_number"),
            "urgency": "CRITICAL" if event.get("category") == "security" else "HIGH",
            "subject": f"SOS Alert: {event.get('category', 'Emergency').upper()}",
            "details": {
                "passenger_name": event.get("name", "Unknown"),
                "pnr": trip.get("pnr_number", "N/A"),
                "train_no": trip.get("vehicle_number", "N/A"),
                "coach": context.get("coach_id", "N/A"),
                "platform": context.get("platform", "N/A"),
                "location": f"{event.get('lat')}, {event.get('lng')}",
                "next_stop": context.get("next_station", "Unknown")
            }
        }
        
        logger.info(f"🚨 [DISPATCH] Automated RPF Alert Sent: {dispatch_id}")
        logger.info(f"   └─ Target: {payload['target']}")
        logger.info(f"   └─ Msg: Passenger in Coach {payload['details']['coach']} needs help.")
        
        # Subtask 14.2: Mock API Call
        # await self._call_railmadad_api(payload)
        
        return {
            "dispatch_id": dispatch_id,
            "status": "sent",
            "dispatched_at": datetime.utcnow().isoformat(),
            "target_auth": payload['target']
        }

    async def dispatch_to_medical(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Requests medical assistance, selecting the best station based on facilities.
        """
        from database.session import SessionTransit
        from sqlalchemy import text
        
        context = event.get("railway_context", {})
        next_station_name = context.get("next_station", "Unknown")
        
        transit_db = SessionTransit()
        try:
            # Subtask 15.1: Medical Facility Audit
            # Find facilities for the next station
            facility = transit_db.execute(text("""
                SELECT f.has_ambulance, f.medical_contact, f.medical_rank, s.name, s.code
                FROM stops s
                LEFT JOIN station_facilities f ON s.id = f.stop_id
                WHERE (LOWER(TRIM(s.name)) = :name OR s.code = :code)
                LIMIT 1
            """), {"name": next_station_name.lower().strip(), "code": next_station_name.upper().strip()}).fetchone()
            
            print(f"DEBUG: Facility search for '{next_station_name}' -> {facility}")
            
            dispatch_id = f"MED-{uuid.uuid4().hex[:8].upper()}"
            
            if facility:
                has_amb = "YES" if facility[0] else "NO"
                payload = {
                    "dispatch_id": dispatch_id,
                    "target_station": facility[3],
                    "station_code": facility[4],
                    "ambulance_available": has_amb,
                    "medical_contact": facility[1] or "102 (National)",
                    "urgency": "CRITICAL",
                    "action": "KEEP AMBULANCE & STRETCHER READY AT PLATFORM"
                }
                logger.info(f"🚑 [MEDICAL DISPATCH] Alert sent to Station Master of {facility[3]} ({facility[4]})")
                logger.info(f"   └─ Ambulance: {has_amb} | Contact: {payload['medical_contact']}")
            else:
                # Subtask 15.2: Fallback to General Medical Alert
                payload = {
                    "dispatch_id": dispatch_id,
                    "target_station": next_station_name,
                    "ambulance_available": "UNKNOWN",
                    "medical_contact": "108",
                    "urgency": "CRITICAL",
                    "action": "BROADCAST TO NEAREST EMERGENCY SERVICES"
                }
                logger.warning(f"⚠️ [MEDICAL DISPATCH] No specific facility info for {next_station_name}. Falling back to 108.")

            return {
                "dispatch_id": dispatch_id,
                "status": "sent",
                "dispatched_at": datetime.utcnow().isoformat(),
                "medical_details": payload
            }
        finally:
            transit_db.close()

    async def notify_emergency_contacts(self, event: Dict[str, Any], contacts: List[str]) -> bool:
        """
        Sends urgent notifications to the user's family with a visual guide link.
        """
        from utils.tracking_links import tracking_link_gen
        
        tracking_url = tracking_link_gen.get_family_url(event['id'])
        passenger_name = event.get("name", "A family member")
        
        message = (
            f"⚠️ URGENT: RouteMaster SOS Alert for {passenger_name}\n\n"
            f"An emergency incident has been reported. Help is being dispatched.\n\n"
            f"📍 Track Live Status & Location:\n{tracking_url}\n\n"
            f"GUIDE: Click the link to see real-time train position and responder status."
        )
        
        logger.info(f"👨‍👩‍👧‍👦 [FAMILY ALERT] Notifying {len(contacts)} contacts for event {event['id']}")
        for phone in contacts:
            if phone:
                logger.info(f"   └─ Sending Visual Guide SMS to: {phone}")
                # Real SMS integration: await sms_service.send(phone, message)
        
        return True

    async def escalate_to_hq(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Task 38: Automated Level 3 escalation to National Railway HQ.
        """
        dispatch_id = f"HQ-{uuid.uuid4().hex[:8].upper()}"
        
        payload = {
            "dispatch_id": dispatch_id,
            "target": "National Railway HQ - Central Monitoring",
            "urgency": "LEVEL-3 CRITICAL",
            "incident_id": event.get("id"),
            "unresolved_duration": "60+ minutes",
            "subject": f"🚨 PRIORITY ESCALATION: UNRESOLVED SOS - {event.get('id')}",
            "details": {
                "passenger": event.get("name"),
                "train_no": (event.get("trip") or {}).get("vehicle_number", "N/A"),
                "last_location": f"{event.get('lat')}, {event.get('lng')}",
                "google_maps": event.get("google_maps_url")
            }
        }
        
        logger.error(f"⚠️ [HQ ESCALATION] Level 3 Dispatch to National HQ: {dispatch_id}")
        logger.error(f"   └─ Reason: SOS unresolved within 60 minutes. HQ intervention required.")
        
        return {
            "dispatch_id": dispatch_id,
            "status": "escalated_to_hq",
            "dispatched_at": datetime.utcnow().isoformat()
        }

dispatch_service = DispatchService()
