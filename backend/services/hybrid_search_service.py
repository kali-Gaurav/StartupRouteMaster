import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import time
from datetime import datetime

from core.route_engine import RouteEngine, route_engine
from config import Config

logger = logging.getLogger(__name__)

class HybridSearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or route_engine

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False
    ) -> List[dict]:
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
            from core.route_engine.constraints import RouteConstraints
            constraints = RouteConstraints(max_transfers=3)
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
                from database.models import Stop
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
            
            return formatted_response

        except Exception as e:
            logger.error(f"Error searching routes for {source} -> {destination}: {e}", exc_info=True)
            return {"source": source, "destination": destination, "routes": {"direct":[], "one_transfer":[], "two_transfer":[], "three_transfer":[]}, "message": str(e)}

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
        from models import Stop
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
