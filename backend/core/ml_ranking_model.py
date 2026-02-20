"""Adapter providing the old `RouteRankingModel` API expected by core modules.

This adapter wraps the canonical `backend.services.route_ranking_predictor`
implementation so existing imports (`backend.core.ml_ranking_model`) keep
working after consolidation.
"""
import asyncio
import logging
from typing import List, Any, Optional

from backend.services.route_ranking_predictor import RouteRankingPredictor

logger = logging.getLogger(__name__)


class RouteRankingModel:
    """Compatibility wrapper that exposes:
      - `loaded` boolean
      - `async def predict(routes, user_context, constraints)`

    Internally uses `RouteRankingPredictor` and maps results back onto
    `Route` objects (sets `ml_score`).
    """

    def __init__(self):
        self._predictor = RouteRankingPredictor()
        # try to load existing model; fall back to untrained predictor
        try:
            self._predictor.load_model()
            self.loaded = getattr(self._predictor, "is_trained", False)
        except Exception:
            self.loaded = False

    async def predict(self, routes: List[Any], user_context: Optional[Any], constraints: Optional[Any] = None) -> List[Any]:
        """Apply predictor to a list of `Route` dataclass instances (or dicts).

        - Uses a thread to call the CPU-bound predictor.
        - Writes the probability into `route.ml_score` (float) and returns
          the list sorted by descending score.
        """
        loop = asyncio.get_running_loop()

        async def _score(route):
            # accept either dataclass-like object (has attributes) or dict
            if isinstance(route, dict):
                features = route
            else:
                # build a minimal dict the predictor understands
                seg0 = None
                try:
                    seg0 = route.segments[0]
                    departure_hour = getattr(seg0, "departure_time", None)
                except Exception:
                    departure_hour = None

                features = {
                    "total_duration_minutes": getattr(route, "total_duration", 0),
                    "total_cost": getattr(route, "total_cost", 0.0),
                    "num_transfers": len(getattr(route, "transfers", [])),
                    "predicted_delay_minutes": getattr(route, "predicted_delay", 0),
                    "departure_hour": getattr(departure_hour, "hour", 12) if departure_hour else 12,
                    "departure_day_of_week": getattr(departure_hour, "weekday", lambda: 0)() if departure_hour else 0,
                    "route_popularity_score": getattr(route, "popularity_score", 0.5),
                }

            # run predictor in threadpool (predictor is synchronous)
            try:
                prob = await loop.run_in_executor(None, self._predictor.predict_booking_probability, features)
            except Exception:
                prob = 0.5
            # attach to route
            try:
                setattr(route, "ml_score", float(prob))
            except Exception:
                # route may be a dict
                if isinstance(route, dict):
                    route["ml_score"] = float(prob)
            return route

        scored = []
        for r in routes:
            scored.append(await _score(r))

        # sort by ml_score descending (fallback to existing `reliability`)
        scored.sort(key=lambda x: getattr(x, "ml_score", x.get("ml_score", 0.0)) if isinstance(x, (dict, object)) else 0.0, reverse=True)
        return scored


__all__ = ["RouteRankingModel"]
