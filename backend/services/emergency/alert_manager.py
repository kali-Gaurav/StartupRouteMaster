import logging
import time
import math
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import SessionLocal, SessionTransit
from database.models import Trip, Booking, StopTime, Stop, TrainLiveUpdate, Route
from services.realtime_ingestion.position_estimator import TrainPositionEstimator

logger = logging.getLogger(__name__)

class EmergencyAlertManager:
    def __init__(self):
        self.db = SessionLocal()
        self.transit_db = SessionTransit()
        self.estimator = TrainPositionEstimator(self.transit_db)

    @staticmethod
    def _classify_threat(event: Dict[str, Any]) -> str:
        text_context = str(event.get("extra", "")).lower()
        history = event.get("chat_history") or []
        for msg in history:
             text_context += " " + str(msg.get("content", "")).lower()
        if any(kw in text_context for kw in ["heart", "pain", "bleeding", "doctor", "hospital", "breathe", "medical"]): return "medical"
        if any(kw in text_context for kw in ["fire", "smoke", "burning"]): return "fire"
        if any(kw in text_context for kw in ["snatch", "thief", "steal", "rob", "gun", "knife", "harass", "following"]): return "security"
        return "unknown"

    @staticmethod
    def _find_nearest_authority(lat: float, lng: float, threat_type: str) -> Optional[Dict[str, Any]]:
        if not lat or not lng: return None
        transit_db = SessionTransit()
        try:
            target_types = ("RPF", "GRP") if threat_type == "security" else ("HOSPITAL", "FIRE") if threat_type in ["medical", "fire"] else ("RPF", "GRP", "HOSPITAL")
            lat_diff, lng_diff = 0.5, 0.5
            placeholders = ', '.join(['?'] * len(target_types))
            query = f"SELECT name, type, contact_number, latitude, longitude, response_time_mins, station_code FROM emergency_authorities WHERE type IN ({placeholders}) AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
            conn = transit_db.connection()
            cursor = conn.connection.cursor()
            params = list(target_types) + [lat - lat_diff, lat + lat_diff, lng - lng_diff, lng + lng_diff]
            cursor.execute(query, params)
            results = cursor.fetchall()
            if not results: return None
            def haversine(la1, lo1, la2, lo2):
                R = 6371.0
                dla, dlo = math.radians(la2-la1), math.radians(lo2-lo1)
                a = math.sin(dla/2)**2 + math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dlo/2)**2
                return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            nearest = min(results, key=lambda x: haversine(lat, lng, x[3], x[4]))
            dist_km = round(haversine(lat, lng, nearest[3], nearest[4]), 2)
            
            # Dynamic ETA Calibration (Task 32)
            # Use DB's pre-computed base response time if available
            db_response_base = nearest[5] or 5.0 
            
            # Assume responder vehicle speed is 40 km/h. travel_time = (dist / 40) * 60
            travel_time_mins = (dist_km / 40.0) * 60
            
            # Total ETA = Base Dispatch Time + Travel Time
            dynamic_eta_mins = round(db_response_base + travel_time_mins)
            
            return {"name": nearest[0], "type": nearest[1], "contact_number": nearest[2], "distance_km": dist_km, "eta_mins": dynamic_eta_mins, "station_code": nearest[6]}
        except Exception: return None
        finally: transit_db.close()

    async def _alert_nearby_trusted_users(self, trip_id: Optional[int], coach: str, excluded_user_id: Optional[str]):
        if not trip_id: return
        from database.models import Booking, User
        from api.websockets import manager
        try:
            # Task 34: Find confirmed passengers on the same trip
            # For now, we search all confirmed passengers on the trip (since coach filtering needs better data)
            nearby = self.db.query(User.supabase_id).join(Booking, User.id == Booking.user_id).filter(
                Booking.trip_id == trip_id, 
                Booking.booking_status == 'confirmed', 
                User.supabase_id != excluded_user_id
            ).all()
            
            if nearby:
                responder_ids = [r[0] for r in nearby if r[0]]
                logger.info(f"📣 [CROWDSOURCE] Alerting {len(responder_ids)} responders on Trip {trip_id}")
                
                # Payload for responders
                alert_payload = {
                    "type": "CROWDSOURCE_SOS_REQUEST",
                    "priority": "high",
                    "trip_id": trip_id,
                    "coach": coach,
                    "message": f"EMERGENCY: A passenger in coach {coach} needs immediate assistance. Please help if you are nearby."
                }
                
                # Broadcast to specific users via WebSocket
                for sid in responder_ids:
                    await manager.send_personal_message(sid, alert_payload)
                    
        except Exception as e:
            logger.error(f"Error in crowdsource alerting: {e}")

    def _get_platform_position(self, coach: str) -> str:
        c = str(coach).upper()
        if c.startswith(('H', 'A', 'B', 'M')): return "Front-Middle (AC Section)"
        if c.startswith('S'): return "Middle-Rear (Sleeper Section)"
        if c.startswith(('GS', 'GEN')): return "Rear (General)"
        return "Middle"

    async def process_sos_alert(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        if raw_event is None:
            logger.error("process_sos_alert received None raw_event")
            return {}
            
        from api.websockets import manager
        from services.realtime_ingestion.live_status_service import LiveStatusService
        from database.models import Stop, TrainLiveUpdate
        
        enriched_event = raw_event.copy()
        
        # 1. Breadcrumbs
        if "location_history" not in enriched_event: enriched_event["location_history"] = []
        if enriched_event.get("lat") and enriched_event.get("lng"):
            enriched_event["location_history"].append({"lat": enriched_event["lat"], "lng": enriched_event["lng"], "ts": datetime.utcnow().isoformat()})
            if len(enriched_event["location_history"]) > 10: enriched_event["location_history"] = enriched_event["location_history"][-10:]

        # 2. Threat Classification & Panic Score
        threat_category = self._classify_threat(enriched_event)
        enriched_event["category"] = threat_category
        from utils.emotional_engine import EmotionalEngine
        history = enriched_event.get("chat_history") or []
        full_text = f"{enriched_event.get('extra', '')} " + " ".join([m.get('content', '') for m in history])
        panic_score = EmotionalEngine.calculate_panic_score(full_text)
        enriched_event["panic_score"] = panic_score
        if panic_score >= 8: enriched_event["priority"] = "critical"

        # 3. High-Risk Profiling
        uid = raw_event.get("user_id")
        if uid:
             from database.models import Profile
             prof = self.db.query(Profile).filter(Profile.user_id == uid).first()
             if prof:
                  enriched_event["passenger_profile"] = {"blood_group": getattr(prof, 'blood_group', 'N/A'), "medical_conditions": getattr(prof, 'medical_conditions', 'None'), "is_high_risk": getattr(prof, 'is_high_risk_passenger', False)}
                  if getattr(prof, 'is_high_risk_passenger', False): enriched_event["priority"] = "critical"
        
        # 4. Live Sync
        trip_data = raw_event.get("trip") or {}
        train_no = trip_data.get("vehicle_number")
        coach = trip_data.get("coach", "Unknown")
        
        if train_no:
            live_svc = LiveStatusService()
            try:
                live_res = await live_svc.get_live_status(train_no)
                if live_res and "raw_data" in live_res:
                    data_list = live_res["raw_data"].get("data", [])
                    curr_stn = next((s for s in data_list if s.get("is_current_station")), data_list[0] if data_list else None)
                    if curr_stn:
                        stn_name = curr_stn.get("station_name")
                        db_stn = self.transit_db.query(Stop).filter(Stop.name.ilike(f"%{stn_name}%")).first()
                        enriched_event.setdefault("railway_context", {}).update({"current_station": stn_name, "platform": curr_stn.get("platform", "Unknown"), "delay": curr_stn.get("delay", "On Time"), "coach_id": coach, "platform_position": self._get_platform_position(coach), "live_lat": db_stn.latitude if db_stn else None, "live_lon": db_stn.longitude if db_stn else None, "source": "Real-time API Sync"})
                        if (not enriched_event.get("lat") or enriched_event.get("lat") == 0) and db_stn:
                            enriched_event["lat"], enriched_event["lng"] = db_stn.latitude, db_stn.longitude
            finally: await live_svc.close_session()

        # 5. Routing & Dispatch
        nearest_auth = self._find_nearest_authority(enriched_event.get("lat", 0.0), enriched_event.get("lng", 0.0), threat_category)
        if nearest_auth: enriched_event["nearest_authority"] = nearest_auth

        from services.emergency.dispatch_service import dispatch_service
        if threat_category == "security": enriched_event["dispatch"] = await dispatch_service.dispatch_to_rpf(enriched_event)
        elif threat_category == "medical": enriched_event["dispatch"] = await dispatch_service.dispatch_to_medical(enriched_event)

        # 6. Family Outreach
        if enriched_event.get("priority") == "critical" and uid:
             family_contacts = ["+91-FAMILY-MOCK"] 
             asyncio.create_task(dispatch_service.notify_emergency_contacts(enriched_event, family_contacts))

        # 7. Emergency Bridge
        if enriched_event.get("priority") == "critical":
             from services.telecom_service import telecom_service
             from database.config import Config
             participants = [enriched_event.get("phone"), enriched_event.get("nearest_authority", {}).get("contact_number"), Config.EMERGENCY_ADMIN_NUMBER or "+91-ADMIN-MOCK"]
             participants = [p for p in participants if p]
             enriched_event["conference_id"] = await telecom_service.bridge_emergency_conference(enriched_event["id"], participants)

        # 8. Crowdsource
        asyncio.create_task(self._alert_nearby_trusted_users(trip_data.get("trip_id"), coach, uid))

        await manager.broadcast_sos(enriched_event)
        return enriched_event

    def __del__(self):
        try: self.db.close()
        except: pass
        try: self.transit_db.close()
        except: pass
