import asyncio
import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import time
from datetime import datetime

from backend.core.route_engine import RouteEngine, route_engine
from backend.config import Config
from backend.services.seat_allocation import SeatAllocationService, CoachType
from backend.services.verification_engine import verification_service
from backend.services.journey_reconstruction import JourneyReconstructionEngine
from backend.database.models import Stop, Trip, Route

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or route_engine
        self.reconstructor = JourneyReconstructionEngine(db)

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False
    ) -> Dict[str, Any]:
        """
        Performs route search using the unified RailwayRouteEngine.
        Returns routes formatted for the frontend BackendRoutesResponse.
        """
        logger.info(f"Unified Route Search: {source} -> {destination} on {travel_date}")
        start_time = time.time()
        
        try:
            # Parse travel_date to datetime
            dt = datetime.strptime(travel_date, "%Y-%m-%d")
            
            # Use constraints from budget if provided
            from backend.core.route_engine.constraints import RouteConstraints
            constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
            if budget_category == "budget":
                constraints.max_transfers = 3 # Allow more transfers for budget
                
            internal_routes = await self.route_engine.search_routes(
                source_code=source,
                destination_code=destination,
                departure_date=dt,
                constraints=constraints
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Route search (RAPTOR) found {len(internal_routes)} routes in {duration_ms}ms.")
            
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
            
            for rt in internal_routes:
                num_transfers = len(rt.segments) - 1
                formatted_rt = self._format_route_for_frontend(rt)
                
                # Collect station info for the 'stations' dictionary
                from backend.database.models import Stop
                for seg in rt.segments:
                    for stop_id in [seg.departure_stop_id, seg.arrival_stop_id]:
                        if str(stop_id) not in formatted_response["stations"]:
                            stop = self.db.query(Stop).filter(Stop.id == stop_id).first()
                            if stop:
                                formatted_response["stations"][str(stop_id)] = {
                                    "code": stop.code,
                                    "name": stop.name,
                                    "city": stop.city,
                                    "state": stop.state
                                }

                if num_transfers == 0:
                    formatted_response["routes"]["direct"].append(formatted_rt)
                elif num_transfers == 1:
                    formatted_response["routes"]["one_transfer"].append(formatted_rt)
                elif num_transfers == 2:
                    formatted_response["routes"]["two_transfer"].append(formatted_rt)
                else:
                    formatted_response["routes"]["three_transfer"].append(formatted_rt)
            
            # --- JOURNEY LIST FOR INTEGRATED FLOW ---
            journeys = []
            for rt in internal_routes:
                num_transfers = len(rt.segments) - 1
                total_duration_hours = rt.total_duration // 60
                total_duration_mins = rt.total_duration % 60
                
                # Create JourneyInfoResponse compatible data
                journey_id = f"rt_{rt.segments[0].trip_id}_{int(rt.segments[0].departure_time.timestamp())}"
                
                journeys.append({
                    "journey_id": journey_id,
                    "num_segments": len(rt.segments),
                    "distance_km": rt.total_distance,
                    "travel_time": f"{total_duration_hours:02d}:{total_duration_mins:02d}",
                    "num_transfers": num_transfers,
                    "is_direct": num_transfers == 0,
                    "cheapest_fare": rt.total_cost,
                    "premium_fare": rt.total_cost * 2.2, # Simplified premium fare logic
                    "has_overnight": any((seg.arrival_time - seg.departure_time).days > 0 for seg in rt.segments),
                    "availability_status": "AVAILABLE"
                })
            
            formatted_response["journeys"] = journeys
            return formatted_response

        except Exception as e:
            logger.error(f"Error searching routes for {source} -> {destination}: {e}", exc_info=True)
            return {"source": source, "destination": destination, "routes": {"direct":[], "one_transfer":[], "two_transfer":[], "three_transfer":[]}, "message": str(e), "journeys": []}

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
        from backend.utils.validation import validate_date_string
        parsed_date = validate_date_string(travel_date_str, allow_past=False)
        if not parsed_date:
            return {"success": False, "message": "Invalid travel date"}

        # Extract trip_id from journey_id if possible
        trip_id = None
        if journey_id.startswith("rt_"):
            parts = journey_id.split("_")
            if len(parts) >= 2:
                trip_id = parts[1]

        # Use Database to find trip and stops
        from backend.database.models import StopTime
        
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
        
        from backend.database.models import CoachType as ModelCoachType
        # Mapping frontend preferences to model coach types if needed
        # Assuming coach_preference matches CoachType enum strings
        
        seat_allocation = seat_service.allocate_seats_for_booking(
            trip_id=str(trip.id),
            passengers=dummy_passengers,
            coach_preference=coach_preference
        )
        
        # Verification
        verification = await verification_service.verify_journey(
            journey=journey,
            travel_date=parsed_date,
            coach_preference=coach_preference,
            passenger_age=passenger_age,
            concession_type=concession_type
        )
        
        total_duration_hours = journey.total_travel_time_mins // 60
        total_duration_mins = journey.total_travel_time_mins % 60
        
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
            "verification": {
                "overall_status": verification.overall_status.value,
                "is_bookable": verification.is_bookable,
                "seat_check": {
                    "status": verification.seat_verification.status.value,
                    "available": verification.seat_verification.available_seats,
                    "message": verification.seat_verification.message
                },
                "schedule_check": {
                    "status": verification.schedule_verification.status.value,
                    "delay_minutes": verification.schedule_verification.delay_minutes,
                    "message": verification.schedule_verification.message
                },
                "restrictions": verification.restrictions,
                "warnings": verification.warnings
            },
            "fare_breakdown": {
                "base_fare": verification.fare_verification.base_fare,
                "gst": verification.fare_verification.GST,
                "total_fare": verification.fare_verification.total_fare,
                "cancellation_charges": verification.fare_verification.cancellation_charges,
                "applicable_discounts": verification.fare_verification.applicable_discounts
            },
            "can_unlock_details": verification.is_bookable
        }

    def _format_route_for_frontend(self, rt) -> dict:
        """Helper to format internal Route object to frontend BackendDirectRoute or similar"""
        if not rt.segments:
            return {}

        # If it's direct, use the first segment
        if len(rt.segments) == 1:
            seg = rt.segments[0]
            return {
                "train_no": seg.train_number,
                "train_name": seg.train_name,
                "departure": seg.departure_time.strftime("%H:%M"),
                "arrival": seg.arrival_time.strftime("%H:%M"),
                "time_minutes": seg.duration_minutes,
                "time_str": f"{seg.duration_minutes // 60}h {seg.duration_minutes % 60}m",
                "fare": seg.fare,
                "availability": "AVAILABLE", # Default to AVAILABLE if not checked
                "distance": seg.distance_km
            }
        
        # If it's multi-transfer, format as expected by frontend
        res = {
            "type": "one_transfer" if len(rt.segments) == 2 else ("two_transfer" if len(rt.segments) == 3 else "three_transfer"),
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
        from backend.models import Stop
        stop = self.db.query(Stop).filter(Stop.name.ilike(f"%{station_name}%")).first()
        return stop.id if stop else None

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
