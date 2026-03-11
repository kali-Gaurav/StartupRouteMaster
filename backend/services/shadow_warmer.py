import asyncio
import logging
import time
from typing import Dict, Set, List

from services.jit_manager import jit_manager
from core.ml_models.route_predictor import route_predictor
from services.feedback_loop import feedback_loop

logger = logging.getLogger("shadow-warmer")

class ShadowWarmer:
    """
    Subtask 1.13: Predictive Cache Pre-fetching.
    """
    def __init__(self):
        self.warmed_routes: Set[str] = set()

    async def warm_by_intent(self, client_id: str, intent: str, path: str):
        # VITAL: Skip warming for health/docs/root
        if any(x in path for x in ["health", "docs", "openapi.json"]) or path == "/":
            return

        await feedback_loop.record_prediction(client_id, intent, path)
        
        from core.metrics import jit_metrics
        jit_metrics.prewarms_triggered += 1
        
        available_nodes = jit_manager.nodes.keys()
        
        if intent == "SEARCH":
            if "DATABASE" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("DATABASE"))
            if "CACHE" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("CACHE"))
            asyncio.create_task(self._prefetch_user_context(client_id))
            
        elif intent == "STATUS":
            if "GRAPH" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("GRAPH"))
            if "ML_MODELS" in available_nodes:
                asyncio.create_task(jit_manager.ensure_ready("ML_MODELS"))

    async def _prefetch_user_context(self, client_id: str):
        try:
            from services.multi_layer_cache import multi_layer_cache
            cache_key = f"user_recent:{client_id}"
            await multi_layer_cache.get(cache_key)
        except Exception: pass

    async def predictive_graph_warm(self, origin_code: str):
        predictions = await route_predictor.predict_top_destinations(origin_code)
        for dest, prob in predictions:
            if prob > 0.8:
                pass

shadow_warmer = ShadowWarmer()
