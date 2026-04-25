import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseRoutingEngine, RoutingRequest, RoutingResponse
from core.data_structures import Route, RouteSegment, TransferConnection
from services.providers.rapid_multimodal import RapidMultimodalProvider
from schemas.multimodal import TransportMode

logger = logging.getLogger(__name__)

class MultimodalEngine(BaseRoutingEngine):
    """
    [Titan:Omniscient] The Multimodal Tier.
    This engine doesn't look at our database; it looks at the WORLD.
    It triggers external API fetches for Flights/Buses when a Hub is reached.
    """
    
    def __init__(self):
        super().__init__()
        self.provider = RapidMultimodalProvider()

    @property
    def engine_id(self) -> str:
        return "multimodal_nexus_v1"

    async def init(self):
        self.status = "HEALTHY"

    async def find_routes(self, request: RoutingRequest) -> List[Route]:
        """
        Multimodal Discovery Logic:
        1. If source/destination are Hubs with Airports/Terminals -> Fetch Flights.
        2. If distance > 500km -> Favor Flights.
        3. If distance < 500km -> Favor Buses.
        [Task 12.10] Tier Check: Zero API for Backbone.
        """
        from .constraints import DiscoveryModel
        if request.constraints.discovery_model == DiscoveryModel.BACKBONE:
            return []

        from services.rapidapi_provider import rapidapi_provider
        if not rapidapi_provider.is_healthy or rapidapi_provider.quota_latch_active:
            logger.debug("⏩ [MM:SKIP] RapidAPI not available or quota exceeded. Skipping multimodal discovery.")
            return []

        if not request.source_code or not request.destination_code:
            return []

        # [Subtask 12.1] API Fetch Logic
        tasks = [
            self.provider.search_flights(request.source_code, request.destination_code, request.departure_date),
            self.provider.search_buses(request.source_code, request.destination_code, request.departure_date)
        ]
        
        # Parallel fetch to keep latency low
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        flights: List[Any] = results[0] if not isinstance(results[0], Exception) else []
        buses: List[Any] = results[1] if not isinstance(results[1], Exception) else []
        if not isinstance(flights, list):
            flights = []
        if not isinstance(buses, list):
            buses = []
        
        all_segments = flights + buses
        
        routes = []
        for seg in all_segments:
            # Convert MultimodalSegment to Route object
            # Note: A single flight is a 1-segment route
            route = Route(
                journey_id=f"mm_{seg.mode.lower()}_{seg.provider}_{datetime.now().timestamp()}",
                segments=[self._to_route_segment(seg)],
                total_duration=seg.duration_minutes,
                total_cost=seg.price
            )
            # Tag with metadata for the scorer
            route.metadata = {
                "engine": "multimodal",
                "mode": seg.mode,
                "is_live": True
            }
            routes.append(route)
            
        return routes

    def _to_route_segment(self, seg) -> RouteSegment:
        """Mapper from Multimodal schema to Internal RouteSegment."""
        # This allows the Scorer to treat a FlightLeg just like a TrainLeg
        return RouteSegment(
            from_station=seg.source_code,
            to_station=seg.destination_code,
            departure=seg.departure_time,
            arrival=seg.arrival_time,
            train_name=f"{seg.mode}: {seg.provider}",
            train_no=seg.metadata.get("flight_no", "MM-API"),
            distance=0, # Computed if needed
            travel_class="MM-DEFAULT",
            fare=seg.price
        )
