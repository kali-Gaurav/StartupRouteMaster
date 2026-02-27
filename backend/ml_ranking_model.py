"""Top-level compatibility shim for legacy imports of `ml_ranking_model`.

Some modules use `from ...ml_ranking_model import RouteRankingModel` (relative to
`backend`) or `from ml_ranking_model import RouteRankingModel` —
export the adapter implemented in `backend.core.ml_ranking_model` so both
styles continue to work after consolidation.
"""
from core.ml_ranking_model import RouteRankingModel

__all__ = ["RouteRankingModel"]
