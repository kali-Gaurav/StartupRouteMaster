import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from ...database import SessionLocal
from ...database.models import Stop

from ..validator.validation_manager import create_validation_manager_with_defaults, ValidationProfile, ValidationCategory

from .data_structures import Route, UserContext
from .constraints import RouteConstraints
from .raptor import OptimizedRAPTOR

logger = logging.getLogger(__name__)

class RouteEngine:
    """Main route engine interface"""

    def __init__(self):
        self.raptor = OptimizedRAPTOR(max_transfers=3)
        self.validation_manager = create_validation_manager_with_defaults()

    async def search_routes(self, source_code: str, destination_code: str,
                           departure_date: datetime,
                           constraints: Optional[RouteConstraints] = None,
                           user_context: Optional[UserContext] = None) -> List[Route]:
        """
        Search for routes between source and destination

        Args:
            source_code: Source station code (e.g., 'NDLS')
            destination_code: Destination station code
            departure_date: Departure date and time
            constraints: Route constraints
            user_context: User preferences for personalization

        Returns:
            List of ranked routes
        """
        if constraints is None:
            constraints = RouteConstraints()

        # Get station IDs
        session = SessionLocal()
        try:
            source_stop = session.query(Stop).filter(Stop.code == source_code).first()
            dest_stop = session.query(Stop).filter(Stop.code == destination_code).first()

            if not source_stop or not dest_stop:
                logger.warning(f"Stop not found: {source_code} or {destination_code}")
                return []

            # Same-origin / same-destination -> return empty result (zero-length journey)
            if source_stop.id == dest_stop.id:
                return []

            # Execute RAPTOR search
            routes = await self.raptor.find_routes(
                source_stop.id, dest_stop.id, departure_date, constraints
            )

            # Apply ML ranking if user context provided
            if user_context:
                routes = await self._apply_ml_ranking(routes, user_context)

            return routes

        finally:
            session.close()

    async def _apply_ml_ranking(self, routes: List[Route], user_context: UserContext) -> List[Route]:
        """Apply ML-based ranking and personalization"""
        # Placeholder for ML integration
        # In production, this would call shadow_inference_service
        # For now, just return routes sorted by reliability
        routes.sort(key=lambda r: -r.reliability)
        return routes

    def validate_resilience(self, validation_config: dict = None) -> bool:
        """Facade: run resilience (RT-171—RT-200) validations via OptimizedRAPTOR."""
        return self.raptor.validate_resilience(validation_config)

    def validate_production_excellence(self, validation_config: dict = None) -> bool:
        """Facade: run production-excellence (RT-201—RT-220) validations via OptimizedRAPTOR."""
        return self.raptor.validate_production_excellence(validation_config)

    # ==============================================================================
    # GRAPH MUTATION INTEGRATION
    # ==============================================================================

    async def apply_realtime_updates(self, updates: List[Dict[str, Any]]):
        """Apply real-time updates to the routing graph (Delegated to Graph Logic)"""
        # This needs to access the graph instance. 
        # Since OptimizedRAPTOR manages the graph (or builds it on demand), 
        # a persistent graph manager might be needed for a stateful server.
        # For this refactor, we acknowledge this as a Phase 5 implementation detail.
        pass
