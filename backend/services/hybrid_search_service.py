import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import time

from backend.core.route_engine import RouteEngine, route_engine
from backend.config import Config

logger = logging.getLogger(__name__)

class HybridSearchService:
    def __init__(self, db: Session, route_engine_instance: Optional[RouteEngine] = None):
        self.db = db
        self.route_engine = route_engine_instance or route_engine
        self.external_api_timeout_ms = Config.EXTERNAL_API_TIMEOUT_MS # Default to 500ms

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False
    ) -> List[Dict]:
        """
        Performs route search using railway_manager.db as the sole data source.
        Returns train routes from the local GTFS database.
        """
        logger.info(f"Searching train routes from railway_manager.db: {source} -> {destination}")
        start_time = time.time()
        
        try:
            internal_routes = await self.route_engine.search_routes(
                source=source,
                destination=destination,
                travel_date=travel_date,
                budget_category=budget_category,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Route search completed in {duration_ms}ms, found {len(internal_routes)} routes.")
            return internal_routes

        except Exception as e:
            logger.error(f"Error searching routes for {source} -> {destination}: {e}", exc_info=True)
            return []

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
