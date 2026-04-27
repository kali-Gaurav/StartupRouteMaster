"""
Model-Tier Aware Search API
============================

Provides endpoints for:
  - GET /api/v3/models       → List available routing intelligence tiers
  - POST /api/v3/search      → Tier-aware search (accepts model_tier parameter)
  - GET /api/v3/models/stats  → Synapse telemetry per tier

This is the frontend-facing interface for the multi-model routing system,
analogous to how ChatGPT/Gemini/Claude let users select different models.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from database.session import SessionLocal, get_db
from core.route_engine.synapse import ModelTier, SynapseDispatcher,MODEL_REGISTRY
from core.route_engine.constraints import RouteConstraints
from core.route_engine.base import RoutingRequest
from core.data_structures import Persona, ensure_datetime
from utils.responses import SafeJSONResponse
from utils.limiter import limiter

router = APIRouter(prefix="", tags=["v3-models"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────

class TierSearchRequest(BaseModel):
    """Request schema for the tier-aware search endpoint."""
    source: str = Field(..., description="Source station code (e.g. NDLS)")
    destination: str = Field(..., description="Destination station code (e.g. BCT)")
    date: Optional[str] = Field(None, description="Travel date YYYY-MM-DD")
    model_tier: str = Field(
        "STANDARD",
        description="Routing intelligence tier: LIGHT, STANDARD, or ULTRA_TURBO",
    )
    persona: str = Field("COMFORT", description="User persona: COMFORT, BUDGET, FAST, EMERGENCY, FAMILY")
    limit: int = Field(15, ge=1, le=100, description="Max routes to return")
    preferences: Optional[List[str]] = Field(
        None, description="Optional preferences: safety, comfort, speed, cost"
    )


class ModelInfo(BaseModel):
    """Schema for a single model tier info response."""
    tier: str
    display_name: str
    tagline: str
    description: str
    icon: str
    color: str
    features: List[str]
    typical_latency_ms: int
    typical_yield: int
    cost_factor: float
    max_transfers: int
    reliability_scoring: bool
    safety_scoring: bool
    is_available: bool


# ─────────────────────────────────────────────────────
# Singleton Synapse dispatcher (initialized on first use)
# ─────────────────────────────────────────────────────

_synapse: Optional[SynapseDispatcher] = None


def _get_synapse() -> SynapseDispatcher:
    """Lazy-initialize the Synapse dispatcher from the global route engine."""
    global _synapse
    if _synapse is None:
        from core.route_engine.engine import route_engine
        _synapse = SynapseDispatcher(route_engine.orchestrator)
    return _synapse


# ─────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────

@router.get("/models", response_model=List[ModelInfo])
@limiter.limit("60/minute")
async def list_available_models(request: Request):
    """
    Returns the list of available routing intelligence models.

    This powers the frontend model selector dropdown, similar to
    ChatGPT's model picker (GPT-4o / o1 / o3-mini).

    Each model has:
      - display_name: Human-readable name for the UI
      - tagline: Short marketing-style description
      - icon/color: For rendering model badges
      - features: List of enabled capabilities
      - typical_latency_ms: Expected response time
      - cost_factor: Relative compute cost
    """
    try:
        synapse = _get_synapse()
        models = synapse.get_available_models()
        return models
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        # Return static fallback from registry
        return [
            {
                "tier": tier.value,
                "display_name": profile.get("display_name", profile.get("name", tier.value.title())),
                "tagline": profile.get("tagline", profile.get("description", "")),
                "description": profile.get("description", ""),
                "icon": profile.get("icon", ""),
                "color": profile.get("color_hex", "#64748b"),
                "features": list(profile.get("features", [])),
                "typical_latency_ms": int(profile.get("typical_latency_ms", 0)),
                "typical_yield": int(profile.get("typical_yield", 0)),
                "cost_factor": float(profile.get("cost_factor", profile.get("discovery_score", 1.0))),
                "max_transfers": int(profile.get("max_transfers", 0)),
                "reliability_scoring": bool(profile.get("reliability_scoring", True)),
                "safety_scoring": bool(profile.get("safety_scoring", True)),
                "is_available": True,
                "available_engines": len(profile.get("engine_ids", [])),
                "total_engines": len(profile.get("engine_ids", [])),
            }
            for tier, profile in MODEL_REGISTRY.items()
        ]


@router.post("/search")
@limiter.limit("60/minute")
async def tier_aware_search(
    request: Request,
    search_request: TierSearchRequest,
    db: Session = Depends(get_db),
):
    """
    Tier-aware search endpoint.

    Accepts a `model_tier` parameter that controls which routing
    intelligence model is used:

      - **LIGHT**: Ultra-fast direct routes (≤100ms)
      - **STANDARD**: Balanced multi-transfer routing (~300ms)
      - **ULTRA_TURBO**: Deep discovery with ML scoring (~1500ms)

    Example request:
    ```json
    {
      "source": "NDLS",
      "destination": "BCT",
      "date": "2026-04-15",
      "model_tier": "ULTRA_TURBO",
      "preferences": ["safety", "comfort"]
    }
    ```
    """
    start_time = time.time()

    # Validate model tier
    try:
        tier = ModelTier(search_request.model_tier.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_MODEL_TIER",
                "message": f"Unknown model tier: '{search_request.model_tier}'. "
                           f"Valid tiers: {[t.value for t in ModelTier]}",
                "valid_tiers": [t.value for t in ModelTier],
            },
        )

    # Parse persona
    try:
        persona = Persona(search_request.persona.upper())
    except (ValueError, KeyError):
        persona = Persona.COMFORT

    # Build travel date
    travel_date_str = search_request.date or datetime.now().strftime("%Y-%m-%d")
    try:
        departure_date = datetime.strptime(travel_date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: '{travel_date_str}'. Use YYYY-MM-DD.",
        )

    # Build constraints
    constraints = RouteConstraints(
        persona=persona,
        max_results=search_request.limit,
    )

    # Apply preference hints
    if search_request.preferences:
        if "safety" in search_request.preferences:
            constraints.women_safety_priority = True
            constraints.weights.safety = 2.0
        if "speed" in search_request.preferences:
            constraints.weights.time = 3.0
        if "cost" in search_request.preferences:
            constraints.weights.cost = 2.5
        if "comfort" in search_request.preferences:
            constraints.weights.comfort = 3.0

    # Build RoutingRequest  
    from utils.station_utils import resolve_stations
    source_stop, dest_stop = resolve_stations(
        db, search_request.source, search_request.destination
    )
    if not source_stop or not dest_stop:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "STATION_NOT_FOUND",
                "message": f"Could not resolve stations: "
                           f"source={search_request.source}, "
                           f"destination={search_request.destination}",
            },
        )

    routing_request = RoutingRequest(
        source_code=search_request.source.upper(),
        destination_code=search_request.destination.upper(),
        src_cluster_ids=[int(source_stop.id)],
        dst_cluster_ids=[int(dest_stop.id)],
        departure_date=departure_date,
        constraints=constraints,
        limit=search_request.limit,
        db_session=db,
    )

    # Dispatch through Synapse
    synapse = _get_synapse()
    model_meta = MODEL_REGISTRY.get(tier)
    if model_meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown model tier: {tier}")

    try:
        result = await asyncio.wait_for(
            synapse.search(routing_request, model_tier=tier),
            timeout=int(model_meta.get("timeout_ms", 5000)) / 1000.0 + 2.0,  # grace buffer
        )
    except asyncio.TimeoutError:
        display_name = model_meta.get('display_name', model_meta.get('name', getattr(tier, 'value', str(tier)).title()))
        return SafeJSONResponse(
            status_code=504,
            content={
                "error": True,
                "message": f"{display_name} search timed out. "
                           f"Try RouteMaster Light for faster results.",
                "model_tier": getattr(tier, 'value', str(tier)),
                "retry_after": 30,
            },
        )
    except Exception as e:
        logger.error(f"Tier search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal routing error")

    # Serialize routes
    journeys = []
    for route in result.routes:
        segments = []
        for seg in route.segments:
            departure_time = ensure_datetime(seg.departure_time, departure_date)
            arrival_time = ensure_datetime(seg.arrival_time, departure_date)
            segments.append({
                "train_number": seg.train_number,
                "train_name": getattr(seg, "train_name", ""),
                # All naming conventions for station codes
                "departure_station": getattr(seg, "departure_code", ""),
                "arrival_station": getattr(seg, "arrival_code", ""),
                "from_station_code": getattr(seg, "departure_code", ""),
                "to_station_code": getattr(seg, "arrival_code", ""),
                "from_station": getattr(seg, "departure_code", ""),
                "to_station": getattr(seg, "arrival_code", ""),
                "departure_time": departure_time.isoformat() if departure_time else None,
                "arrival_time": arrival_time.isoformat() if arrival_time else None,
                "duration_minutes": seg.duration_minutes,
                "duration": seg.duration_minutes,
                "distance_km": getattr(seg, "distance_km", 0),
                "distance": getattr(seg, "distance_km", 0),
                "fare": getattr(seg, "fare", 0),
                "departure_platform": getattr(seg, "departure_platform", "—"),
                "arrival_platform": getattr(seg, "arrival_platform", "—"),
            })

        transfers = []
        for t in (route.transfers or []):
            transfers.append({
                "from_station": getattr(t, "from_station_code", ""),
                "to_station": getattr(t, "to_station_code", ""),
                "wait_minutes": getattr(t, "wait_time_minutes", 0),
                "type": getattr(t, "transfer_type", "same_station"),
            })

        num_transfers = len(route.transfers or [])
        jid = getattr(route, "journey_id", None) or route.metadata.get("journey_id", f"model_{len(journeys)}")
        journeys.append({
            "journey_id": jid,
            "segments": segments,
            "legs": segments,  # frontend alias
            "transfers": transfers,
            # Duration — both naming conventions
            "total_duration_minutes": route.total_duration,
            "total_duration": route.total_duration,
            # Distance — both naming conventions
            "total_distance_km": getattr(route, "total_distance", 0),
            "total_distance": getattr(route, "total_distance", 0),
            # Cost
            "total_cost": getattr(route, "total_cost", 0),
            "total_fare": getattr(route, "total_cost", 0),
            # Transfers
            "transfer_count": num_transfers,
            "num_transfers": num_transfers,
            # Scoring
            "score": getattr(route, "score", 0),
            "reliability_score": route.metadata.get("reliability_score", getattr(route, "reliability", 0.85)),
            "safety_score": route.metadata.get("safety_score", getattr(route, "safety_score", 1.0)),
            "availability_status": route.metadata.get("live_availability", "AVAILABLE"),
            "delay_probability": route.metadata.get("delay_probability"),
            # Metadata
            "engine_used": route.metadata.get("engine", "unknown"),
            "model_tier": route.metadata.get("model_tier", tier.value),
            "model_display_name": route.metadata.get("model_display_name", ""),
            "is_locked": getattr(route, "is_locked", False),
            "metadata": route.metadata,
        })

    # [Task F4] Apply Route Locks and Masks (Monetization Engine)
    user_id = None
    plan_tier = "FREE"
    try:
        from api.dependencies import get_current_user_optional
        user = await get_current_user_optional(request, db)
        if user:
            user_id = user.id
            if hasattr(user, "subscription") and user.subscription:
                plan_tier = user.subscription.plan_tier
    except Exception:
        pass

    from services.unlock_service import apply_route_locks
    journeys = apply_route_locks(
        db=db,
        routes=journeys,
        user_id=user_id,
        departure_date=travel_date_str,
        plan_tier=plan_tier,
        preview_count=0  # For testing, let's lock everything to see the UI. Change to 1 for prod teaser.
    )

    total_latency_ms = int((time.time() - start_time) * 1000)

    return {
        "model": {
            "tier": tier.value,
            "display_name": result.model_display_name or model_meta.get("display_name", model_meta.get("name", "")),
            "icon": model_meta.get("icon", ""),
            "color": model_meta.get("color_hex", "#64748b"),
            "tagline": model_meta.get("tagline", model_meta.get("description", "")),
        },
        "search": {
            "source": search_request.source.upper(),
            "destination": search_request.destination.upper(),
            "date": travel_date_str,
            "persona": persona.value,
        },
        "results": {
            "journeys": journeys,
            "count": len(journeys),
            "total_available": result.yield_count,
        },
        "performance": {
            "total_latency_ms": total_latency_ms,
            "engine_latency_ms": result.total_latency_ms or result.latency_ms,
            "engines_invoked": result.engines_invoked,
            "engines_succeeded": result.engines_succeeded,
            "engines_failed": result.engines_failed,
        },
    }


@router.get("/models/stats")
@limiter.limit("30/minute")
async def get_model_stats(request: Request):
    """
    Returns per-tier telemetry: search counts, average latency,
    and average yield for each model tier.
    """
    try:
        synapse = _get_synapse()
        return {
            "telemetry": synapse.get_telemetry(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Model stats error: {e}")
        return {"telemetry": {}, "error": str(e)}
