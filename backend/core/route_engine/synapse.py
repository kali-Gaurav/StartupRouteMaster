from enum import Enum
from typing import Dict, List, Any, Optional
import time
import logging
from .base import RoutingRequest, RoutingResponse

logger = logging.getLogger("synapse")

class ModelTier(str, Enum):
    LIGHT = "light"           # Fastpath / Direct only (low latency, low discovery)
    STANDARD = "standard"    # Turbo + RAPTOR (medium budget)
    PREMIUM = "premium"      # Turbo + RAPTOR (high budget) + MLP ranker
    ULTRA_TURBO = "ultra_turbo" # Experimental high-yield engines

MODEL_REGISTRY = {
    ModelTier.LIGHT: {
        "name": "RouteMaster Light",
        "description": "Optimized for speed. Ideal for direct routes and major hubs.",
        "latency_sla": "100ms",
        "discovery_score": 0.4,
        "icon": "⚡"
    },
    ModelTier.STANDARD: {
        "name": "RouteMaster Standard",
        "description": "The balanced choice for most journeys.",
        "latency_sla": "800ms",
        "discovery_score": 0.75,
        "icon": "🚀"
    },
    ModelTier.PREMIUM: {
        "name": "RouteMaster Premium",
        "description": "Deep discovery for complex multi-leg journeys.",
        "latency_sla": "2500ms",
        "discovery_score": 0.95,
        "icon": "💎"
    },
    ModelTier.ULTRA_TURBO: {
        "name": "RouteMaster Ultra-Turbo",
        "description": "Experimental high-yield engine for maximum route density.",
        "latency_sla": "5000ms",
        "discovery_score": 0.99,
        "icon": "🏎️"
    }
}

class SynapseDispatcher:
    """
    Synapse Dispatcher (Tier-Aware Router)
    ======================================
    Orchestrates search requests across different model tiers by adjusting
    search budgets, algorithms, and engines.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.stats = {
            tier: {"requests": 0, "avg_latency_ms": 0.0, "yield_sum": 0} 
            for tier in ModelTier
        }

    async def search(self, request: RoutingRequest, model_tier: ModelTier = ModelTier.STANDARD) -> RoutingResponse:
        start_ts = time.perf_counter()
        
        # Adjust search budget and constraints based on tier
        if model_tier == ModelTier.LIGHT:
            request.constraints.max_transfers = 1
            request.metadata["search_budget_ms"] = 200
            # Force skip heavy RAPTOR discovery if needed, or use specific light config
            request.metadata["engine_priority"] = ["ultra_turbo", "turbo", "fastpath"]
        
        elif model_tier == ModelTier.STANDARD:
            request.constraints.max_transfers = 2
            request.metadata["search_budget_ms"] = 1000
            request.metadata["engine_priority"] = ["ultra_turbo", "turbo", "fastpath", "raptor"]
            
        elif model_tier == ModelTier.PREMIUM:
            request.constraints.max_transfers = 3
            request.metadata["search_budget_ms"] = 3000
            request.metadata["engine_priority"] = ["ultra_turbo", "turbo", "raptor", "hybrid"]
            
        elif model_tier == ModelTier.ULTRA_TURBO:
            request.constraints.max_transfers = 4
            request.metadata["search_budget_ms"] = 8000
            request.metadata["engine_priority"] = ["ultra_turbo", "turbo", "raptor", "hybrid", "tbr_router"]

        # Track usage
        self.stats[model_tier]["requests"] += 1
        
        # Dispatch to orchestrator
        response = await self.orchestrator.find_routes(request)
        
        # Update stats
        latency = (time.perf_counter() - start_ts) * 1000
        n = self.stats[model_tier]["requests"]
        old_avg = self.stats[model_tier]["avg_latency_ms"]
        self.stats[model_tier]["avg_latency_ms"] = (old_avg * (n-1) + latency) / n
        self.stats[model_tier]["yield_sum"] += response.yield_count
        
        return response

    def get_available_models(self) -> List[Dict[str, Any]]:
        models: List[Dict[str, Any]] = []
        for tier, meta in MODEL_REGISTRY.items():
            models.append({
                "tier": tier.value,
                "display_name": meta.get("display_name", meta.get("name", tier.value.title())),
                "tagline": meta.get("tagline", meta.get("description", "")),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", ""),
                "color": meta.get("color_hex", "#64748b"),
                "features": list(meta.get("features", [])),
                "typical_latency_ms": int(meta.get("typical_latency_ms", 0)),
                "typical_yield": int(meta.get("typical_yield", 0)),
                "cost_factor": float(meta.get("cost_factor", meta.get("discovery_score", 1.0))),
                "max_transfers": int(meta.get("max_transfers", 0)),
                "reliability_scoring": bool(meta.get("reliability_scoring", True)),
                "safety_scoring": bool(meta.get("safety_scoring", True)),
                "is_available": True,
            })
        return models

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            tier: {
                "requests": stats["requests"],
                "avg_latency_ms": round(stats["avg_latency_ms"], 2),
                "avg_yield": round(stats["yield_sum"] / max(1, stats["requests"]), 1)
            }
            for tier, stats in self.stats.items()
        }
