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
        """Task 17/19/23: Multi-factor classification with Phonetic Hashing."""
        from utils.phonetic_hasher import safety_hasher
        
        text_context = str(event.get("extra", "")).lower()
        history = event.get("chat_history") or []
        for msg in history:
             text_context += " " + str(msg.get("content", "")).lower()
        
        # 1. Physical Factor
        g_force = float(event.get("accel_g_force", 0.0))
        post_impact_motion = float(event.get("post_impact_motion", 1.0))
        is_fall = g_force > 4.0 and post_impact_motion < 0.2
        
        # 2. Phonetic Keyword Classification (Task 23)
        category = "unknown"
        if safety_hasher.match(text_context, ["heart", "pain", "bleeding", "doctor", "hospital", "breathe", "medical"]):
            category = "medical"
        elif safety_hasher.match(text_context, ["fire", "smoke", "burning"]):
            category = "fire"
        elif safety_hasher.match(text_context, ["help", "save", "bachao", "snatch", "thief", "steal", "rob", "gun", "knife", "harass"]):
            category = "security"
        
        # 3. Sensor Fusion Priority Boost
        if is_fall:
            event["priority"] = "critical"
            event["extra"] = f"{event.get('extra', '')} | 🚨 HEURISTIC: POSSIBLE UNCONSCIOUS FALL (Motion: {post_impact_motion})"
            category = "medical_emergency_fall"
        elif g_force > 4.0:
            event["priority"] = "critical"
            event["extra"] = f"{event.get('extra', '')} | ⚠️ HIGH-G IMPACT DETECTED ({g_force}G)"
            if category == "unknown": category = "accident"
            
        return category

    @staticmethod
    def _find_nearest_authority(lat: float, lng: float, threat_type: str, station_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not lat or not lng: return None
        transit_db = SessionTransit()
        try:
            # 1. Fast Path - Pre-computed (Task 4)
            if station_id:
                query_fast = text("""
                    SELECT a.name, a.type, a.contact_number, a.latitude, a.longitude, a.response_time_mins, a.station_code, a.id
                    FROM emergency_authorities a
                    JOIN stations s ON s.nearest_authority_id = a.id
                    WHERE s.id = :sid
                """)
                fast_res = transit_db.execute(query_fast, {"sid": station_id}).fetchone()
                if fast_res:
                    return {
                        "name": fast_res[0], "type": fast_res[1], "contact_number": fast_res[2],
                        "distance_km": 0.0, "eta_mins": fast_res[5] or 5, "station_code": fast_res[6],
                        "source": "precomputed_matrix"
                    }

            # 2. Regular Path - Spatial Query (Task 32)
            target_types = ("RPF", "GRP") if threat_type == "security" else ("HOSPITAL", "FIRE") if threat_type in ["medical", "fire"] else ("RPF", "GRP", "HOSPITAL")
            lat_diff, lng_diff = 0.5, 0.5
            placeholders = ', '.join([':t' + str(i) for i in range(len(target_types))])
            params = {f"t{i}": t for i, t in enumerate(target_types)}
            params.update({"min_lat": lat - lat_diff, "max_lat": lat + lat_diff, "min_lng": lng - lng_diff, "max_lng": lng + lng_diff})
            
            query = text(f"SELECT name, type, contact_number, latitude, longitude, response_time_mins, station_code FROM emergency_authorities WHERE type IN ({placeholders}) AND latitude BETWEEN :min_lat AND :max_lat AND longitude BETWEEN :min_lng AND :max_lng")
            results = transit_db.execute(query, params).fetchall()
            
            if results:
                def haversine(la1, lo1, la2, lo2):
                    R = 6371.0
                    dla, dlo = math.radians(la2-la1), math.radians(lo2-lo1)
                    a = math.sin(dla/2)**2 + math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dlo/2)**2
                    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                
                nearest = min(results, key=lambda x: haversine(lat, lng, x[3], x[4]))
                dist_km = round(haversine(lat, lng, nearest[3], nearest[4]), 2)
                dynamic_eta = round((nearest[5] or 5.0) + (dist_km / 40.0) * 60)
                return {"name": nearest[0], "type": nearest[1], "contact_number": nearest[2], "distance_km": dist_km, "eta_mins": dynamic_eta, "station_code": nearest[6], "source": "spatial_query"}

        except Exception as e:
            logger.error(f"DB Error in routing: {e}")
            
        # 3. Offline Path - Safety Graph Fallback (Task 10)
        try:
            graph_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'safety_graph.bin')
            if os.path.exists(graph_path):
                import pickle
                with open(graph_path, 'rb') as f:
                    graph = pickle.load(f)
                
                if station_id and station_id in graph['stations']:
                    aid = graph['stations'][station_id]['auth_id']
                    if aid in graph['authorities']:
                        auth = graph['authorities'][aid]
                        return {"name": auth['name'], "type": auth['type'], "contact_number": auth['phone'], "distance_km": 0.0, "eta_mins": 5, "source": "offline_graph_direct"}
                
                def graph_dist(a):
                    dla = math.radians(a['lat']-lat); dlo = math.radians(a['lng']-lng)
                    v = math.sin(dla/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(a['lat']))*math.sin(dlo/2)**2
                    return 6371.0 * 2 * math.atan2(math.sqrt(v), math.sqrt(1-v))
                
                if graph['authorities']:
                    closest_id = min(graph['authorities'].keys(), key=lambda k: graph_dist(graph['authorities'][k]))
                    auth = graph['authorities'][closest_id]
                    return {"name": auth['name'], "type": auth['type'], "contact_number": auth['phone'], "distance_km": round(graph_dist(auth), 2), "eta_mins": 10, "source": "offline_graph_fallback"}
        except Exception as e:
            logger.error(f"Offline Routing Failure: {e}")
            
        finally:
            try: transit_db.close()
            except: pass
        return None

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
        
        # 1. Breadcrumbs (Delta-Encoded for Task 5)
        if "location_history" not in enriched_event: enriched_event["location_history"] = []
        new_lat = enriched_event.get("lat")
        new_lng = enriched_event.get("lng")
        
        if new_lat and new_lng:
            history = enriched_event["location_history"]
            if not history:
                # First point: Full storage
                history.append({
                    "lat": new_lat, "lng": new_lng, 
                    "ts": datetime.utcnow().isoformat(),
                    "is_full": True
                })
            else:
                last = history[-1]
                # If last was encoded, we need to find the base to calculate delta
                # For simplicity, we compare against the VERY FIRST point (anchor)
                base = history[0]
                d_lat = round(new_lat - base["lat"], 6)
                d_lng = round(new_lng - base["lng"], 6)
                
                # Check if movement is significant (> 1 meter ~ 0.00001 degrees)
                if abs(d_lat) > 0.00001 or abs(d_lng) > 0.00001:
                    history.append({
                        "dl": d_lat, "dg": d_lng, # Delta Lat, Delta Lng
                        "dt": int((datetime.utcnow() - datetime.fromisoformat(base["ts"])).total_seconds()),
                        "is_delta": True
                    })
            
            if len(history) > 20: enriched_event["location_history"] = [history[0]] + history[-19:]

        # 2. Threat Classification & Panic Score
        pre_transcript = enriched_event.get("pre_trigger_transcript")
        if pre_transcript:
            enriched_event["extra"] = f"[PRE-SOS CONTEXT]: {pre_transcript} | " + str(enriched_event.get("extra", ""))
            
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
                        if db_stn:
                            enriched_event.setdefault("railway_context", {}).update({
                                "current_station": stn_name,
                                "station_id": db_stn.id, # Map ID for Task 4 O(1) Lookup
                                "platform": curr_stn.get("platform", "Unknown"),
                                "delay": curr_stn.get("delay", "On Time"),
                                "coach_id": coach,
                                "platform_position": self._get_platform_position(coach),
                                "live_lat": db_stn.latitude,
                                "live_lon": db_stn.longitude,
                                "source": "Real-time API Sync"
                            })
                            if (not enriched_event.get("lat") or enriched_event.get("lat") == 0):
                                enriched_event["lat"], enriched_event["lng"] = db_stn.latitude, db_stn.longitude
            finally: await live_svc.close_session()

        # 5. Routing & Dispatch
        rail_ctx = enriched_event.get("railway_context", {})
        stn_id = rail_ctx.get("station_id") # Assuming we mapped station_id in Step 4
        
        nearest_auth = self._find_nearest_authority(
            enriched_event.get("lat", 0.0), 
            enriched_event.get("lng", 0.0), 
            threat_category,
            station_id=stn_id
        )
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
