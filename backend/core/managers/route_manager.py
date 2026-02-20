import logging
from typing import Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ..route_engine.raptor import OptimizedRAPTOR, HybridRAPTOR
from ..route_engine.hub import HubManager, HubConnectivityTable
from ..route_engine.data_structures import Route, UserContext
from ..route_engine.constraints import RouteConstraints

logger = logging.getLogger(__name__)


class RouteManager:
    """High-level facade that encapsulates route-searching engines and ML ranking.

    - Hosts the RAPTOR implementations (OptimizedRAPTOR / HybridRAPTOR)
    - Exposes a single `find_routes` method used by higher-level callers
    - Keeps the `raptor` instance accessible for backward compatibility
    """

    def __init__(self, hub_manager: HubManager, graph_manager=None, max_transfers: int = 3,
                 raptor: Optional[OptimizedRAPTOR] = None):
        self.hub_manager = hub_manager
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.raptor = raptor or HybridRAPTOR(self.hub_manager, max_transfers=max_transfers)
        self.graph_manager = graph_manager

        # ML ranking model is still owned by the route manager (exposed for backward-compat)
        try:
            from ...ml_ranking_model import RouteRankingModel
            self.route_ranking_model = RouteRankingModel()
        except Exception:
            self.route_ranking_model = None

    def set_hub_table(self, table: HubConnectivityTable):
        """Inject precomputed hub connectivity into the RAPTOR instance."""
        if table:
            self.raptor.set_hub_table(table)

    async def find_routes(self, source_stop_id: int, dest_stop_id: int,
                          departure_date: datetime, constraints: RouteConstraints,
                          graph=None, user_context: Optional[UserContext] = None) -> List[Route]:
        """Delegate to RAPTOR and apply ML ranking when available."""
        routes = await self.raptor.find_routes(source_stop_id, dest_stop_id, departure_date, constraints, graph=graph)

        # Apply ML ranking if provided
        if user_context and self.route_ranking_model and self.route_ranking_model.loaded:
            try:
                ranked = await self.route_ranking_model.predict(routes, user_context, constraints)
                return ranked
            except Exception as e:
                logger.warning("RouteManager: ML ranking failed — falling back to default sort: %s", e)

        # Fallback: sort by score + reliability
        routes.sort(key=lambda r: (r.score if getattr(r, 'score', None) is not None else 9999, -r.reliability))
        return routes
