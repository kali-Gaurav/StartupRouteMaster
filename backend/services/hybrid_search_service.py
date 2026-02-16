import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import time

from backend.services.route_engine import RouteEngine
from backend.services.multi_modal_route_engine import MultiModalRouteEngine
from backend.services.external_api_service import fetch_external_routes
from backend.config import Config

logger = logging.getLogger(__name__)

class HybridSearchService:
    def __init__(self, db: Session, route_engine: RouteEngine):
        self.db = db
        self.route_engine = route_engine
        self.multi_modal_engine = MultiModalRouteEngine()
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
        Performs a hybrid search for routes, prioritizing external real-time APIs
        and falling back to the internal graph if external services are too slow or fail.
        """
        internal_routes = []
        external_routes = []
        
        # Attempt to fetch from external API with a timeout
        try:
            logger.info(f"Attempting external API fetch for {source} -> {destination}")
            external_task = asyncio.create_task(
                fetch_external_routes(
                    source=source,
                    destination=destination,
                    travel_date=travel_date,
                    budget_category=budget_category
                )
            )
            
            # Use asyncio.wait_for for timeout
            external_routes = await asyncio.wait_for(
                external_task, timeout=self.external_api_timeout_ms / 1000.0
            )
            logger.info(f"External API fetch successful for {source} -> {destination}, found {len(external_routes)} routes.")
            # If external API returns results, prioritize them
            return external_routes
            
        except asyncio.TimeoutError:
            logger.warning(f"External API for {source} -> {destination} timed out after {self.external_api_timeout_ms}ms. Falling back to internal graph.")
        except ConnectionError as e:
            logger.error(f"External API connection error for {source} -> {destination}: {e}. Falling back to internal graph.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during external API fetch for {source} -> {destination}: {e}. Falling back to internal graph.", exc_info=True)

        # For commission-based strategy, skip external APIs and focus on internal static data
        # with multi-modal intelligence
        logger.info(f"Performing internal graph search for {source} -> {destination} (multi_modal={multi_modal})")
        start_time_internal = time.time()
        try:
            if multi_modal:
                # Use multi-modal engine
                self.multi_modal_engine.load_graph_from_db(self.db)
                # Assume stops are resolved to IDs
                source_stop_id = self._resolve_stop_id(source)
                dest_stop_id = self._resolve_stop_id(destination)
                if source_stop_id and dest_stop_id:
                    from datetime import datetime
                    travel_date_obj = datetime.fromisoformat(travel_date).date()
                    journeys = self.multi_modal_engine.search_single_journey(source_stop_id, dest_stop_id, travel_date_obj)
                    internal_routes = [self._convert_journey_to_route(j) for j in journeys]
                else:
                    internal_routes = []
            else:
                internal_routes = await self.route_engine.search_routes(
                    source=source,
                    destination=destination,
                    travel_date=travel_date,
                    budget_category=budget_category,
                )
            duration_ms_internal = int((time.time() - start_time_internal) * 1000)
            logger.info(f"Internal graph search for {source} -> {destination} completed in {duration_ms_internal}ms, found {len(internal_routes)} routes.")

            # Enhance with multi-modal planning if requested
            if multi_modal and internal_routes:
                enhanced_routes = self._enhance_with_multimodal_suggestions(
                    internal_routes, source, destination, travel_date, budget_category
                )
                return enhanced_routes

        except RuntimeError as e:
            logger.error(f"Internal route engine error for {source} -> {destination}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during internal graph search for {source} -> {destination}: {e}", exc_info=True)

        return internal_routes

    def _enhance_with_multimodal_suggestions(
        self,
        routes: List[Dict],
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None
    ) -> List[Dict]:
        """
        Enhance routes with multi-modal planning suggestions and commission bias.
        Prioritizes high-commission partners and suggests optimal combinations.
        """
        enhanced_routes = routes.copy()

        # Commission partner mapping (higher commission = higher priority)
        commission_partners = {
            "RailYatri": {"commission": 0.08, "type": "train", "description": "Best railway commissions"},
            "RedBus": {"commission": 0.06, "type": "bus", "description": "Top bus booking partner"},
            "MakeMyTrip": {"commission": 0.07, "type": "flight", "description": "Premium flight bookings"},
            "AbhiBus": {"commission": 0.05, "type": "bus", "description": "Regional bus specialist"},
            "Goibibo": {"commission": 0.06, "type": "flight", "description": "Flight & hotel combos"}
        }

        # Add commission metadata to existing routes
        for route in enhanced_routes:
            # Bias towards RailYatri for train routes (highest commission)
            route["commission_partner"] = "RailYatri"
            route["commission_rate"] = commission_partners["RailYatri"]["commission"]
            route["booking_url"] = f"https://railway.example.com/book?route={route.get('id', 'default')}"
            route["multi_modal_suggestion"] = "Direct train route with best commission rates"

        # Add placeholder multi-modal suggestions (when we have bus/flight data)
        # For now, suggest combinations that would be optimal
        multimodal_suggestions = [
            {
                "id": f"multimodal_train_bus_{len(enhanced_routes)}",
                "source": source,
                "destination": destination,
                "total_duration_minutes": 480,  # 8 hours (longer but cheaper)
                "total_cost": 120.0,  # Cheaper combined
                "num_transfers": 1,
                "segments": [
                    {
                        "mode": "train",
                        "departure": "08:00",
                        "arrival": "12:00",
                        "cost": 80.0,
                        "operator": "Indian Railways"
                    },
                    {
                        "mode": "bus",
                        "departure": "13:00",
                        "arrival": "16:00",
                        "cost": 40.0,
                        "operator": "Private Bus"
                    }
                ],
                "commission_partner": "RedBus",  # Bus partner for the combination
                "commission_rate": commission_partners["RedBus"]["commission"],
                "booking_url": f"https://redbus.example.com/combo?from={source}&to={destination}&date={travel_date}",
                "multi_modal_suggestion": "Train + Bus combo: Save money with overnight train to city, then connecting bus",
                "pareto_optimal": True
            },
            {
                "id": f"multimodal_flight_bus_{len(enhanced_routes) + 1}",
                "source": source,
                "destination": destination,
                "total_duration_minutes": 300,  # 5 hours (fastest)
                "total_cost": 250.0,  # More expensive
                "num_transfers": 1,
                "segments": [
                    {
                        "mode": "flight",
                        "departure": "06:00",
                        "arrival": "08:00",
                        "cost": 200.0,
                        "operator": "Air India"
                    },
                    {
                        "mode": "bus",
                        "departure": "09:00",
                        "arrival": "11:00",
                        "cost": 50.0,
                        "operator": "Airport Shuttle"
                    }
                ],
                "commission_partner": "MakeMyTrip",  # Flight partner
                "commission_rate": commission_partners["MakeMyTrip"]["commission"],
                "booking_url": f"https://makemytrip.example.com/flight-bus?from={source}&to={destination}&date={travel_date}",
                "multi_modal_suggestion": "Flight + Bus combo: Fastest option with premium flight commissions",
                "pareto_optimal": True
            }
        ]

        # Add multimodal suggestions to the results
        enhanced_routes.extend(multimodal_suggestions)

        # Sort by commission rate descending (highest commission first)
        enhanced_routes.sort(key=lambda x: x.get("commission_rate", 0), reverse=True)

        logger.info(f"Enhanced {len(routes)} routes with {len(multimodal_suggestions)} multi-modal suggestions")
        return enhanced_routes

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
