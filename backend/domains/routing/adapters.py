"""
Compatibility Adapter Layer for Routing Engine

Implements Strangler Pattern for safe migration of route engines.

This adapter allows old code to continue using the legacy API while
internally using the new consolidated RailwayRouteEngine from domains/routing/.

CAUTION: This is a transitional file. Once migration is complete and tested,
this adapter can be removed after updating all callers.
"""

import logging
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime

# Handle imports for both running from backend/ and startupV2/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from domains.routing.engine import RailwayRouteEngine
    from database import SessionLocal
except ImportError:
    from backend.domains.routing.engine import RailwayRouteEngine
    from backend.database import SessionLocal

try:
    from services.hybrid_search_service import HybridSearchService
except ImportError:
    from backend.services.hybrid_search_service import HybridSearchService

logger = logging.getLogger(__name__)


class LegacyHybridSearchAdapter:
    """
    Compatibility adapter for the old HybridSearchService API.

    Maps old HybridSearchService method signatures to the new RailwayRouteEngine.

    DEPRECATION NOTICE:
    This adapter exists only for backwards compatibility during Phase 1 migration.
    New code should use RailwayRouteEngine directly from domains/routing/.

    Feature Flag: USE_NEW_ROUTING_ENGINE in config.py
    """

    def __init__(self, new_engine: Optional[RailwayRouteEngine] = None):
        """
        Initialize the adapter.

        Args:
            new_engine: The new RailwayRouteEngine instance.
                       If None, will be created.
        """
        self.new_engine = new_engine or RailwayRouteEngine()
        logger.info("🟡 LegacyHybridSearchAdapter initialized (backwards compatibility mode)")

    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search routes using the legacy API signature.

        This method adapts the old HybridSearchService signature to the new engine.

        Args:
            source: Source station code/name
            destination: Destination station code/name
            travel_date: ISO format date string
            budget_category: Optional budget category (ignored in new engine)

        Returns:
            List of route dictionaries
        """
        logger.debug(f"[LEGACY ADAPTER] search_routes: {source} -> {destination} on {travel_date}")

        try:
            # Parse date
            if isinstance(travel_date, str):
                departure_date = datetime.fromisoformat(travel_date)
            else:
                departure_date = travel_date

            # Call new engine
            routes = await self.new_engine.search_routes(
                source_code=source,
                destination_code=destination,
                departure_date=departure_date,
                constraints=None,
                user_context=None,
            )

            # Convert Route objects to dictionaries for backwards compatibility
            result = []
            for route in routes:
                route_dict = {
                    "id": getattr(route, "id", None),
                    "source": source,
                    "destination": destination,
                    "departure_time": getattr(route, "departure_time", None),
                    "arrival_time": getattr(route, "arrival_time", None),
                    "duration": getattr(route, "duration", None),
                    "cost": getattr(route, "cost", None),
                    "transfers": getattr(route, "transfers", 0),
                    "vendor": getattr(route, "vendor", "IRCTC"),
                }
                result.append(route_dict)

            logger.info(
                f"[LEGACY ADAPTER] Found {len(result)} routes (via new engine)"
            )
            return result

        except Exception as e:
            logger.error(f"[LEGACY ADAPTER] Error in search_routes: {e}", exc_info=True)
            return []

    def _enhance_with_multimodal_suggestions(
        self,
        routes: List[Dict],
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Legacy method for multimodal enhancement (trains only in new system).

        In the new consolidated engine, multimodal is handled differently.
        This method just returns routes as-is.

        Args:
            routes: List of route dictionaries
            source: Source station
            destination: Destination station
            travel_date: Travel date
            budget_category: Budget category

        Returns:
            Routes (unchanged - trains-only mode)
        """
        logger.debug(
            f"[LEGACY ADAPTER] multimodal enhancement requested (returning trains-only)"
        )
        return routes

    def _resolve_stop_id(self, station_name: str) -> Optional[int]:
        """
        Legacy method to resolve station name to stop ID.

        Uses database directly.

        Args:
            station_name: Station name or code

        Returns:
            Stop ID or None
        """
        try:
            try:
                from database.models import Stop
            except ImportError:
                from backend.database.models import Stop

            db = SessionLocal()
            try:
                stop = (
                    db.query(Stop)
                    .filter(Stop.name.ilike(f"%{station_name}%"))
                    .first()
                )
                return stop.id if stop else None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[LEGACY ADAPTER] Error resolving stop: {e}")
            return None

    def _convert_journey_to_route(self, journey: Dict) -> Dict:
        """
        Legacy method to convert journey to route format.

        Args:
            journey: Journey dictionary

        Returns:
            Route dictionary
        """
        legs = journey.get("legs", [])
        if not legs:
            return {}

        first_leg = legs[0]
        last_leg = legs[-1]

        return {
            "id": journey.get("journey_id", "multi-modal"),
            "source": first_leg.get("departure_stop"),
            "destination": last_leg.get("arrival_stop"),
            "departure_time": first_leg.get("departure_time"),
            "arrival_time": last_leg.get("arrival_time"),
            "duration": journey.get("total_duration"),
            "cost": journey.get("total_cost"),
            "transfers": journey.get("transfers"),
            "legs": legs,
            "mode": "multi-modal",
            "operator": "Multi-Modal Service",
        }


# Singleton instance for backwards compatibility
_adapter_instance: Optional[LegacyHybridSearchAdapter] = None


def get_legacy_adapter(new_engine: Optional[RailwayRouteEngine] = None) -> LegacyHybridSearchAdapter:
    """
    Get or create the legacy adapter singleton.

    Args:
        new_engine: Optional new engine instance

    Returns:
        LegacyHybridSearchAdapter instance
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = LegacyHybridSearchAdapter(new_engine)
    return _adapter_instance
