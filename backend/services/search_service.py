import asyncio
import logging
import json
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import time
from datetime import datetime, timedelta

from core.route_engine import RouteEngine, route_engine
from database.config import Config
from services.seat_allocation import SeatAllocationService, CoachType
from services.verification_engine import verification_service, RouteVerificationEngine
from services.verification_orchestrator import VerificationOrchestrator
from services.journey_reconstruction import JourneyReconstructionEngine
from database.models import Stop, Trip, Route
from core.redis import redis_client
from utils.station_utils import resolve_stations

logger = logging.getLogger(__name__)

# Request coalescing to prevent search storms (Topic 4)
_inflight_searches: Dict[str, asyncio.Event] = {}
_search_results: Dict[str, Any] = {}

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or route_engine
        self.reconstructor = JourneyReconstructionEngine(db)
        self.verification_engine = RouteVerificationEngine(db)
        self.verification_orchestrator = VerificationOrchestrator(db)

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False,
        women_safety_mode: bool = False  # Added for Phase 2 Product USP
    ) -> Dict[str, Any]:
        """
        Performs route search using the unified RailwayRouteEngine.
        Returns routes formatted for the frontend BackendRoutesResponse.
        Includes Redis caching and Request Coalescing.
        """
        from utils import metrics

        # --- CACHE CHECK ---
        cache_key = f"search:{source}:{destination}:{travel_date}:{budget_category}:{multi_modal}:{women_safety_mode}"
        
        # 1. Check Request Coalescing (Topic 4: Search Storm Prevention)
        if cache_key in _inflight_searches:
            logger.info(f"COALESCE: Waiting for in-flight search: {cache_key}")
            await _inflight_searches[cache_key].wait()
            return _search_results.get(cache_key)

        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"CACHE HIT for search: {cache_key}")
                return json.loads(cached_data)
        except Exception as ce:
            logger.warning(f"Cache lookup failed: {ce}")

        # Start Coalescing
        _inflight_searches[cache_key] = asyncio.Event()
        
        try:
            logger.info(f"Unified Route Search: {source} -> {destination} on {travel_date} (Safety: {women_safety_mode})")
            overall_start = time.time()
            
            # Resolve station names/codes to Stop objects
            source_stop, dest_stop = resolve_stations(self.db, source, destination)
            if not source_stop or not dest_stop:
                missing = []
                if not source_stop: missing.append(f"source '{source}'")
                if not dest_stop: missing.append(f"destination '{destination}'")
                result = {
                    "source": source, 
                    "destination": destination, 
                    "routes": {"direct":[], "one_transfer":[], "two_transfer":[], "three_transfer":[]}, 
                    "message": f"Could not resolve: {', '.join(missing)}", 
                    "journeys": []
                }
                _search_results[cache_key] = result
                return result
            
            # Use resolved stop_id for the search engine (this is usually the code like 'NDLS')
            source_code = source_stop.stop_id
            dest_code = dest_stop.stop_id

            # Parse travel_date to datetime (handle both YYYY-MM-DD and YYYY-MM-DD HH:MM:SS)
            if " " in travel_date:
                dt = datetime.strptime(travel_date, "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime.strptime(travel_date, "%Y-%m-%d")
                # Default to 08:00 AM if no time provided for search window
                dt = dt.replace(hour=8, minute=0)
            
            # Use constraints from budget if provided
            from core.route_engine.constraints import RouteConstraints
            constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
            if budget_category == "budget":
                constraints.max_transfers = 3 # Allow more transfers for budget
                
            # Apply Product USP: Women Safety Mode
            if women_safety_mode:
                constraints.women_safety_priority = True
                constraints.avoid_night_layovers = True
                # Prioritize safety in scoring weights
                constraints.weights.safety = 1.0
                constraints.weights.comfort = 0.5
                constraints.weights.time = 0.3
                constraints.weights.cost = 0.2
                logger.info(f"Applying Women Safety Constraints for {source} -> {destination}")

            # measure graph compute separately
            graph_start = time.time()
            internal_routes = await self.route_engine.search_routes(
                source_code=source_code,
                destination_code=dest_code,
                departure_date=dt,
                constraints=constraints
            )
            metrics.ROUTE_GRAPH_COMPUTE_MS.observe((time.time() - graph_start) * 1000)

            # Developer convenience: if no routes are found and we are in development mode,
            if not internal_routes and Config.ENVIRONMENT == "development":
                logger.warning("No internal routes found; injecting dummy development route.")
                # build minimal Dummy objects matching expected attributes used later
                class DevSeg:
                    def __init__(self):
                        self.trip_id = "dev_1"
                        self.departure_stop_id = 1
                        self.arrival_stop_id = 2
                        now = datetime.utcnow()
                        self.departure_time = now
                        self.arrival_time = now + timedelta(days=0, hours=2) # Ensure timedelta is available
                        self.train_number = "00000"
                        self.train_name = "Dev Express"
                        self.duration_minutes = 120
                        self.fare = 0
                class DevRoute:
                    def __init__(self):
                        seg = DevSeg()
                        self.segments = [seg]
                        self.transfers = []
                        self.total_duration = seg.duration_minutes
                        self.total_distance = 100
                        self.total_cost = 0
                internal_routes = [DevRoute()]

            duration_ms = int((time.time() - overall_start) * 1000)
            logger.info(f"Route search (RAPTOR) found {len(internal_routes)} routes in {duration_ms}ms.")
            metrics.ROUTE_GENERATION_LATENCY_MS.observe(duration_ms)

            # Format results for frontend BackendRoutesResponse
            formatted_response = {
                "source": source,
                "destination": destination,
                "routes": {
                    "direct": [],
                    "one_transfer": [],
                    "two_transfer": [],
                    "three_transfer": []
                },
                "stations": {},
                "journey_message": f"Found {len(internal_routes)} journey options."
            }
            
            # --- OPTIMIZED STATION LOOKUP ---
            all_stop_ids = set()
            for rt in internal_routes:
                for seg in rt.segments:
                    all_stop_ids.add(seg.departure_stop_id)
                    all_stop_ids.add(seg.arrival_stop_id)
            
            if all_stop_ids:
                stops = self.db.query(Stop).filter(Stop.id.in_(list(all_stop_ids))).all()
                for stop in stops:
                    formatted_response["stations"][str(stop.id)] = {
                        "code": stop.code or stop.stop_id,
                        "name": stop.name,
                        "city": stop.city,
                        "state": stop.state
                    }

            station_codes_by_id: Dict[int, str] = {int(sid): s["code"] for sid, s in formatted_response["stations"].items()}
            route_candidates: List[Dict[str, Any]] = []
            journeys = []
            
            # --- SINGLE PASS FOR CATEGORIZATION, FARE, AND JOURNEYS ---
            from core.pricing.fare_calculator import get_fare_for_train
            
            # Map budget to default coach
            budget_to_class = {
                "economy": "SL",
                "standard": "3A",
                "premium": "2A",
                "all": "SL"
            }
            preferred_class = budget_to_class.get(budget_category, "SL")

            for rt in internal_routes:
                # 1. Fare Calculation
                total_fare = 0
                for seg in rt.segments:
                    try:
                        from_code = station_codes_by_id.get(seg.departure_stop_id) or self._lookup_stop_code(seg.departure_stop_id)
                        to_code = station_codes_by_id.get(seg.arrival_stop_id) or self._lookup_stop_code(seg.arrival_stop_id)
                        
                        fare_details = None
                        if from_code and to_code and seg.train_number:
                            fare_details = get_fare_for_train(self.db, seg.train_number, from_code, to_code, preferred_class)
                        
                        if fare_details and fare_details.get("total_fare"):
                            total_fare += fare_details["total_fare"]
                        else:
                            total_fare += (seg.fare or 0)
                    except Exception as e:
                        logger.error(f"Fare calc error: {e}")
                        total_fare += (seg.fare or 0)
                
                rt.total_cost = total_fare
                
                # 2. Categorization for formatted_response
                num_transfers = len(rt.transfers)
                formatted_rt = self._format_route_for_frontend(rt)
                if num_transfers == 0:
                    formatted_response["routes"]["direct"].append(formatted_rt)
                elif num_transfers == 1:
                    formatted_response["routes"]["one_transfer"].append(formatted_rt)
                elif num_transfers == 2:
                    formatted_response["routes"]["two_transfer"].append(formatted_rt)
                else:
                    formatted_response["routes"]["three_transfer"].append(formatted_rt)
                
                # 3. Construct Journey List for integrated flow (DetailedJourneyResponse)
                total_duration_hours = rt.total_duration // 60
                total_duration_mins = rt.total_duration % 60
                journey_id = f"rt_{rt.segments[0].trip_id}_{int(rt.segments[0].departure_time.timestamp())}"
                
                # Format legs for this journey
                legs = []
                for seg in rt.segments:
                    legs.append({
                        "train_number": seg.train_number,
                        "train_name": seg.train_name,
                        "from_station_code": station_codes_by_id.get(seg.departure_stop_id) or self._lookup_stop_code(seg.departure_stop_id),
                        "to_station_code": station_codes_by_id.get(seg.arrival_stop_id) or self._lookup_stop_code(seg.arrival_stop_id),
                        "departure_time": seg.departure_time.isoformat(),
                        "arrival_time": seg.arrival_time.isoformat(),
                        "duration_minutes": seg.duration_minutes,
                        "distance_km": seg.distance_km,
                        "fare": seg.fare,
                        "mode": "rail"
                    })

                # Format transfers for this journey
                transfers = []
                for t in rt.transfers:
                    transfers.append({
                        "station_name": t.station_name,
                        "station_id": t.station_id,
                        "wait_minutes": t.duration_minutes,
                        "arrival_time": t.arrival_time.isoformat() if t.arrival_time != datetime.min else None,
                        "departure_time": t.departure_time.isoformat() if t.departure_time != datetime.max else None
                    })

                journeys.append({
                    "journey_id": journey_id,
                    "num_segments": len(rt.segments),
                    "distance_km": rt.total_distance,
                    "travel_time": f"{total_duration_hours:02d}:{total_duration_mins:02d}",
                    "num_transfers": num_transfers,
                    "is_direct": num_transfers == 0,
                    "cheapest_fare": rt.total_cost,
                    "premium_fare": round(rt.total_cost * 2.2, 2),
                    "has_overnight": any((seg.arrival_time - seg.departure_time).days > 0 for seg in rt.segments),
                    "availability_status": "AVAILABLE",
                    "legs": legs,
                    "transfers": transfers,
                    "score": getattr(rt, 'score', 0.0)
                })
                
                # 4. Route Candidates for verification
                first_seg = rt.segments[0]
                last_seg = rt.segments[-1]
                route_candidates.append({
                    "journey_id": journey_id,
                    "train_no": first_seg.train_number,
                    "from_code": station_codes_by_id.get(first_seg.departure_stop_id) or self._lookup_stop_code(first_seg.departure_stop_id),
                    "to_code": station_codes_by_id.get(last_seg.arrival_stop_id) or self._lookup_stop_code(last_seg.arrival_stop_id),
                    "from_stop_id": first_seg.departure_stop_id,
                    "to_stop_id": last_seg.arrival_stop_id
                })

            # --- VERIFICATION ENRICHMENT ---
            verification_results = []
            try:
                verification_candidates = route_candidates[:3]
                verif_start = time.time()
                verification_results = await self.verification_orchestrator.verify_top_routes(
                    verification_candidates,
                    dt,
                    coach_preference="AC_THREE_TIER",
                    quota="GN"
                )
                metrics.ROUTE_VERIFICATION_LATENCY_MS.observe((time.time() - verif_start) * 1000)
            except Exception as ve:
                logger.warning(f"Verification enrichment failed: {ve}")

            # compute product metrics if verification was successful
            if verification_results:
                try:
                    success_cnt = sum(1 for r in verification_results if r.get("verified"))
                    ratio = success_cnt / len(verification_results)
                    metrics.VERIFICATION_SUCCESS_RATE.set(ratio)
                    metrics.TOP3_VERIFIED_RATIO.set(ratio)
                except Exception:
                    pass

            verification_lookup = {res["journey_id"]: res for res in verification_results}
            for journey in journeys:
                verification_payload = verification_lookup.get(journey["journey_id"])
                journey["verification_summary"] = verification_payload
                journey["verification_status"] = verification_payload["status"] if verification_payload else "pending"

            formatted_response["journeys"] = journeys
            # capture serialization time
            serialize_start = time.time()
            # (nothing else to do here but we could measure downstream if additional formatting occurs)
            serialize_ms = (time.time() - serialize_start) * 1000
            metrics.ROUTE_RESPONSE_SERIALIZE_MS.observe(serialize_ms)

            # --- STORE IN CACHE ---
            try:
                # Cache for 10 minutes (Config.CACHE_TTL_SECONDS is 300s/5m by default, 
                # but search results can be slightly longer if stable)
                ttl = Config.CACHE_TTL_SECONDS
                redis_client.setex(cache_key, ttl, json.dumps(formatted_response))
                logger.debug(f"CACHE SET for search: {cache_key} with TTL: {ttl}s")
            except Exception as ce:
                logger.warning(f"Cache set failed: {ce}")

            _search_results[cache_key] = formatted_response
            return formatted_response

        except Exception as e:
            logger.error(f"Error searching routes for {source} -> {destination}: {e}", exc_info=True)
            error_res = {"source": source, "destination": destination, "routes": {"direct":[], "one_transfer":[], "two_transfer":[], "three_transfer":[]}, "message": str(e), "journeys": []}
            _search_results[cache_key] = error_res
            return error_res
        finally:
            # Signal completion to other waiting requests (Topic 4)
            event = _inflight_searches.pop(cache_key, None)
            if event:
                event.set()
                # Clean up cached result after a short delay to keep memory low
                asyncio.create_task(self._cleanup_search_result(cache_key))

    async def _cleanup_search_result(self, cache_key: str):
        """Clean up search results from local memory after small delay."""
        await asyncio.sleep(10)
        _search_results.pop(cache_key, None)

    async def unlock_journey_details(
        self,
        journey_id: str,
        travel_date_str: str,
        coach_preference: str = "AC_THREE_TIER",
        passenger_age: int = 30,
        concession_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unlocks detailed journey info with seat allocation and verification.
        """
        from utils.validation import validate_date_string
        parsed_date = validate_date_string(travel_date_str, allow_past=False)
        if not parsed_date:
            return {"success": False, "message": "Invalid travel date"}

        from utils import metrics
        # Extract trip_id from journey_id if possible
        trip_id = None
        if journey_id.startswith("rt_"):
            parts = journey_id.split("_")
            if len(parts) >= 2:
                trip_id = parts[1]

        # Use Database to find trip and stops
        from database.models import StopTime
        
        trip = None
        if trip_id:
             trip = self.db.query(Trip).filter(Trip.trip_id == trip_id).first()
             if not trip and trip_id.isdigit():
                 trip = self.db.query(Trip).filter(Trip.id == int(trip_id)).first()
        
        if not trip:
             return {"success": False, "message": "Trip not found"}

        # Find Source and Destination for the trip
        start_st = self.db.query(StopTime).filter(StopTime.trip_id == trip.id).order_by(StopTime.stop_sequence.asc()).first()
        end_st = self.db.query(StopTime).filter(StopTime.trip_id == trip.id).order_by(StopTime.stop_sequence.desc()).first()
        
        if not start_st or not end_st:
            return {"success": False, "message": "Trip schedule not found"}

        segment = self.reconstructor.reconstruct_single_segment_journey(
            trip_id=trip.id,
            from_stop_id=start_st.stop_id,
            to_stop_id=end_st.stop_id,
            travel_date=parsed_date
        )
        
        if not segment:
            return {"success": False, "message": "Journey reconstruction failed"}
            
        journey = self.reconstructor.reconstruct_complete_journey([segment], parsed_date)
        
        # Seat Allocation
        seat_service = SeatAllocationService(self.db)
        dummy_passengers = [{
            "full_name": "Passenger 1",
            "age": passenger_age,
            "gender": "M"
        }]
        
        from database.models import CoachType as ModelCoachType
        # Mapping frontend preferences to model coach types if needed
        # Assuming coach_preference matches CoachType enum strings
        
        seat_allocation = seat_service.allocate_seats_for_booking(
            trip_id=str(trip.id),
            passengers=dummy_passengers,
            coach_preference=coach_preference
        )
        
        # Verification: use cached live verification when possible
        start_stop = self.db.query(Stop).filter(Stop.id == start_st.stop_id).first()
        end_stop = self.db.query(Stop).filter(Stop.id == end_st.stop_id).first()
        start_code = start_stop.code if start_stop else None
        end_code = end_stop.code if end_stop else None
        train_number = journey.segments[0].train_number if journey.segments else trip.trip_id

        verification_payload = self.verification_engine.get_cached_verification(journey_id)
        if not verification_payload:
            verification_payload = await self.verification_engine.verify_route_async(
                journey_id=journey_id,
                train_number=train_number,
                travel_date=parsed_date,
                coach_preference=coach_preference,
                from_code=start_code,
                to_code=end_code,
                from_stop_id=start_st.stop_id,
                to_stop_id=end_st.stop_id
            )
        
        total_duration_hours = journey.total_travel_time_mins // 60
        total_duration_mins = journey.total_travel_time_mins % 60
        
        # build route graph nodes + edges for frontend visualization
        nodes = []
        for idx, seg in enumerate(journey.segments):
            seg_dict = seg.to_dict()
            seg_dict["segment_id"] = f"seg_{idx}"
            # placeholder fields; can be overwritten by higher-level logic
            seg_dict.setdefault("verification_source", None)
            seg_dict.setdefault("availability_status", "UNKNOWN")
            nodes.append(seg_dict)
        edges = []
        from database.models import Stop
        for idx, tr in enumerate(journey.transfers):
            # transfer connects segment idx -> idx+1
            station_code = None
            try:
                stop = self.db.query(Stop).filter(Stop.id == tr.station_id).first()
                station_code = stop.code if stop else None
            except Exception:
                station_code = None
            edge = {
                "from_segment_id": f"seg_{idx}",
                "to_segment_id": f"seg_{idx+1}",
                "transfer_station_code": station_code or "",
                "wait_minutes": tr.duration_minutes,
                "platform": tr.platform_from or tr.platform_to,
                "transfer_reason": "interchange"
            }
            edges.append(edge)
        route_graph = {
            "nodes": nodes,
            "edges": edges,
            "is_direct": len(journey.transfers) == 0
        }

        rapidapi_calls = sum(1 for called in verification_payload.get("verification_calls", {}).values() if called)
        seat_data = verification_payload.get("seat_availability") or {}
        fare_data = verification_payload.get("fare") or {}
        live_status = verification_payload.get("live_status") or {}
        warnings = [msg for msg in verification_payload.get("errors", []) if msg]
        seat_check = {
            "status": "verified" if seat_data.get("success") else "pending",
            "available": seat_data.get("data", {}).get("availability") if isinstance(seat_data.get("data"), dict) else seat_data.get("data"),
            "message": seat_data.get("error") or (seat_data.get("data", {}).get("message") if isinstance(seat_data.get("data"), dict) else None)
        }
        schedule_check = {
            "status": "verified" if live_status.get("success") else "pending",
            "delay_minutes": None,
            "message": live_status.get("message") or live_status.get("error")
        }
        fare_payload_details = fare_data.get("data") if isinstance(fare_data.get("data"), dict) else {}
        base_fare_candidate = fare_payload_details.get("fare") if isinstance(fare_payload_details.get("fare"), (int, float)) else fare_payload_details.get("fare")
        base_fare = float(base_fare_candidate or 0.0)
        verification_summary = {
            "rapidapi_calls": rapidapi_calls,
            "live_status": live_status,
            "seat_availability": seat_data,
            "fare_verification": fare_data,
            "status": verification_payload.get("status"),
            "errors": warnings,
            "cache_hit": verification_payload.get("cached", False),
            "timestamp": verification_payload.get("timestamp")
        }

        # track unlock latency if we recorded a search timestamp
        from api import integrated_search
        timestamp = integrated_search.SEARCH_TIMESTAMP_CACHE.pop(journey_id, None)
        if timestamp:
            elapsed_ms = (time.time() - timestamp) * 1000
            metrics.SEARCH_TO_UNLOCK_TIME_MS.observe(elapsed_ms)

        overall_status = "verified" if verification_payload.get("verified") else "pending"
        can_unlock = verification_payload.get("verified", False)
        fare_total = float(base_fare)
        verification_block = {
            "overall_status": overall_status,
            "is_bookable": can_unlock,
            "seat_check": seat_check,
            "schedule_check": schedule_check,
            "restrictions": [],
            "warnings": warnings
        }
        fare_breakdown_payload = {
            "base_fare": fare_total,
            "gst": 0.0,
            "total_fare": fare_total,
            "cancellation_charges": 0.0,
            "applicable_discounts": [],
            "payload": fare_payload_details
        }
        return {
            "journey": {
                "journey_id": journey.journey_id,
                "num_segments": journey.num_segments,
                "distance_km": journey.total_distance_km,
                "travel_time": f"{total_duration_hours:02d}:{total_duration_mins:02d}",
                "num_transfers": journey.num_transfers,
                "is_direct": journey.is_direct,
                "cheapest_fare": journey.cheapest_fare,
                "premium_fare": journey.premium_fare,
                "has_overnight": journey.has_overnight,
                "availability_status": journey.availability_status
            },
            "segments": [seg.to_dict() for seg in journey.segments],
            "seat_allocation": {
                "allocated": seat_allocation["allocated_seats"],
                "waiting_list": seat_allocation["waiting_list"],
                "seat_details": seat_allocation["seat_details"]
            },
            "verification": verification_block,
            "fare_breakdown": fare_breakdown_payload,
            "can_unlock_details": can_unlock,
            "route_graph": route_graph,
            "verification_summary": verification_summary
        }

    def _format_route_for_frontend(self, rt) -> dict:
        """Helper to format internal Route object to frontend BackendDirectRoute or similar"""
        if not rt.segments:
            return {}

        # Calculate actual transfer count (not segment count)
        num_transfers = len(rt.transfers)
        
        # If it's direct (0 transfers), aggregate all segments into one
        if num_transfers == 0:
            first_seg = rt.segments[0]
            last_seg = rt.segments[-1]
            return {
                "train_no": first_seg.train_number,
                "train_name": first_seg.train_name,
                "departure": first_seg.departure_time.strftime("%H:%M"),
                "arrival": last_seg.arrival_time.strftime("%H:%M"),
                "time_minutes": rt.total_duration,
                "time_str": f"{rt.total_duration // 60}h {rt.total_duration % 60}m",
                "fare": rt.total_cost,
                "availability": "AVAILABLE", # Default to AVAILABLE if not checked
                "distance": rt.total_distance,
                "num_stops": len(rt.segments)  # Number of stops along the route
            }
        
        # If it's multi-transfer, format as expected by frontend
        res = {
            "type": "one_transfer" if num_transfers == 1 else ("two_transfer" if num_transfers == 2 else "three_transfer"),
            "total_time_minutes": rt.total_duration,
            "total_distance": rt.total_distance,
            "total_fare": rt.total_cost
        }
        
        # Add legs
        for i, seg in enumerate(rt.segments):
            res[f"leg{i+1}"] = {
                "train_no": seg.train_number,
                "train_name": seg.train_name,
                "departure": seg.departure_time.strftime("%H:%M"),
                "arrival": seg.arrival_time.strftime("%H:%M"),
                "time_minutes": seg.duration_minutes,
                "fare": seg.fare
            }
            
        # Add junctions
        for i, trans in enumerate(rt.transfers):
            # For 2-transfer we have junction1, junction2. For 1st transfer in general, use junction1.
            res[f"junction{i+1}"] = trans.station_name
            res[f"waiting{i+1}_minutes"] = trans.duration_minutes

        # Fix naming for junction1, junction2, etc. (Match BackendOneTransferRoute schema)
        if len(rt.segments) == 2:
            res["junction"] = rt.transfers[0].station_name
            res["waiting_time_minutes"] = rt.transfers[0].duration_minutes
        elif len(rt.segments) == 3:
            res["junction1"] = rt.transfers[0].station_name
            res["junction2"] = rt.transfers[1].station_name
            res["waiting1_minutes"] = rt.transfers[0].duration_minutes
            res["waiting2_minutes"] = rt.transfers[1].duration_minutes
            
        return res

    def _enhance_with_multimodal_suggestions(
        self,
        routes: List[Dict],
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None
    ) -> List[Dict]:
        """For trains-only operation, return routes as-is without multi-modal suggestions."""
        logger.info(f"Returning {len(routes)} train routes (no multi-modal enhancement for trains-only mode)")
        return routes

    def _resolve_stop_id(self, station_name: str) -> Optional[int]:
        """Resolve station name to stop ID."""
        from database.models import Stop
        stop = self.db.query(Stop).filter(Stop.name.ilike(f"%{station_name}%")).first()
        return stop.id if stop else None

    def _lookup_stop_code(self, stop_id: Optional[int]) -> Optional[str]:
        if not stop_id:
            return None
        from database.models import Stop
        stop = self.db.query(Stop).filter(Stop.id == stop_id).first()
        return stop.code or stop.stop_id if stop else None

    def _convert_journey_to_route(self, journey: Dict) -> Dict:
        """Convert multi-modal journey to route format."""
        legs = journey.get('legs', [])
        if not legs:
            return {}

        first_leg = legs[0]
        last_leg = legs[-1]

        return {
            "id": journey.get('journey_id', 'multi-modal'),
            "source": first_leg['departure_stop'],
            "destination": last_leg['arrival_stop'],
            "departure_time": first_leg['departure_time'],
            "arrival_time": last_leg['arrival_time'],
            "duration": journey['total_duration'],
            "cost": journey['total_cost'],
            "transfers": journey['transfers'],
            "legs": legs,
            "mode": "multi-modal",
            "operator": "Multi-Modal Service"
        }
