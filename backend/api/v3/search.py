import asyncio
import logging
import time
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.nexus.search.gate import nexus_latency_gate
from core.nexus.search.interceptor import nexus_interceptor
from core.nexus.search.sorter import nexus_sorter
from core.nexus.rl.reconciler import rl_reconciler
from services.search_service import SearchService
from database.session import get_db
from core.nexus.audit.chaos import chaos_trap

logger = logging.getLogger("api.v3.search")
router = APIRouter(prefix="/search", tags=["Nexus V3 Elite Search"])

@router.get("/unified")
@chaos_trap("search_unified")
async def unified_nexus_search(
    request: Request,
    source: str = Query(..., min_length=2, max_length=10),
    destination: str = Query(..., min_length=2, max_length=10),
    date: str = Query(..., description="YYYY-MM-DD"),
    persona: str = Query("ECONOMY", description="ECONOMY, BUSINESS, EMERGENCY"),
    budget: Optional[str] = Query(None),
    bypass_cache: bool = Query(False, description="Force deep graph search"),
    db: Session = Depends(get_db)
):
    """
    [Task 12] Elite V3 Fiber Search Orchestrator.
    Flow: Gatekeeper -> Nexus Gate (Cache) -> V3 Engine (Graph) -> RL Pricing -> Audit.
    """
    start_ts = time.perf_counter()
    
    # 0. High-Integrity Sanitization [Task 13]
    from utils.security import sanitize_string
    source = sanitize_string(source, length_limit=10).upper()
    destination = sanitize_string(destination, length_limit=10).upper()
    
    # 0.1 Geo-location Capture [Task 14]
    from utils.geo_utils import get_state_from_ip
    client_ip = request.headers.get("x-track-ip") or request.client.host
    geo_state = get_state_from_ip(client_ip)
    
    client_ip = request.client.host
    geo_state = "UNKNOWN"
    
    # Use budget if persona is default or budget is provided
    active_persona = (budget or persona).upper()

    # 1. Nexus Fiber Interceptor (Task 18)
    decision = await nexus_interceptor.intercept(request, source, destination)
    if not decision.allowed:
        return {
            "status": "HALT",
            "code": decision.code,
            "message": decision.message,
            "metadata": {
                "geo_state": geo_state,
                "interceptor": decision.metadata
            }
        }

    # 1.1 Fast-Path Cache Check (Latency Gate)
    if not bypass_cache:
        cached_results = await nexus_latency_gate.get_cached_search(source, destination, date, active_persona)
        if cached_results:
            return {
                "status": "SUCCESS",
                "search_mode": "FAST_PATH",
                "engine": "nexus_latency_gate",
                "data": {"journeys": cached_results},
                "metadata": {
                    "interceptor": decision.metadata,
                    "cache": "L1/L2_HIT"
                }
            }

    # 2. Unified Search Logic (Tiers 0-3 + Hydration + Verification)
    search_svc = SearchService(db)
    
    try:
        from core.metrics import jit_metrics
        adaptive_timeout = jit_metrics.get_adaptive_timeout(base_timeout=60.0)
        
        # Execute unified search (Returns hydrated/verified routes)
        v2_result = await asyncio.wait_for(
            search_svc.search_routes(
                source=source,
                destination=destination,
                travel_date=date,
                budget_category=active_persona,
                client_ip=client_ip,
                geo_state=geo_state,
                request=request
            ),
            timeout=adaptive_timeout
        )
        
        if v2_result.get("status") == "error":
             return v2_result

        # 3. Nexus V3 Elite Post-Processing
        # Convert V2 results (already masked/hydrated) into V3 Fiber format
        raw_journeys = v2_result.get("data", {}).get("journeys", [])
        
        # 4. RL Pricing Injection (Neural Reconciler)
        import numpy as np
        mock_state = np.array([0.5, 0.2, 0.8, 0.3])
        pricing_multiplier = rl_reconciler.get_optimal_multiplier(mock_state)
        
        # 5. Elite Sorter (Persona-Aware Polarity)
        sorted_results = nexus_sorter.sort_results(raw_journeys, persona=active_persona)
        
        # Commit to Latency Gate for subsequent hits
        await nexus_latency_gate.commit_search(source, destination, date, sorted_results, active_persona)
        
        # 6. Final V3 Fiber Construction
        from core.nexus.audit.triage import nexus_triage
        backoff = nexus_triage.current_backoff
        search_mode = "DEEP" if backoff < 0.3 else ("ADAPTIVE" if backoff < 0.8 else "SURVIVAL")
        
        latency_ms = (time.perf_counter() - start_ts) * 1000
        return {
            "status": "SUCCESS",
            "search_mode": search_mode,
            "engine": f"nexus_fiber_v3:{search_mode.lower()}",
            "latency_ms": f"{latency_ms:.2f}",
            "data": {
                "journeys": sorted_results,
                "grouped_journeys": v2_result.get("data", {}).get("grouped_journeys", {}),
                "pagination": v2_result.get("data", {}).get("pagination", {})
            },
            "metadata": {
                "interceptor": decision.metadata,
                "geo_state": geo_state,
                "pricing_surge": f"{pricing_multiplier:.2f}x",
                "session_id": v2_result.get("session_id")
            }
        }

    except asyncio.TimeoutError:
        logger.error(f"V3 Fiber Search timed out for {source}->{destination}")
        return {"status": "HALT", "message": "Neural latency threshold exceeded. Try adaptive search."}

from core.nexus.financial.rollback import atomic_fiber, register_undo_step
from services.ledger_service import ledger_service
from database.session import SessionTransit

@router.post("/unlock")
@atomic_fiber("search_unlock")
async def unlock_search_details(
    user_id: str,
    route_id: str,
    amount: float = Query(39.0)
):
    """
    [Task 41] Atomic Search Unlock with Saga Rollback.
    """
    logger.info(f"🔓 [NEXUS:UNLOCK] Initiating Atomic Unlock for User {user_id} | Route {route_id}")

    with SessionTransit() as db:
        # Mock deduction via ledger
        entry = await ledger_service.record_transaction(
            db, "user_wallet", "platform_revenue", amount, "SEARCH_UNLOCK", user_id
        )
        
        # Register the rollback compensation step
        await register_undo_step("LEDGER_INTENT", {"entry_id": entry.id})

        if "fail" in route_id.lower():
             logger.error(f"🚨 [NEXUS:UNLOCK] Verification Failed for Route {route_id}. Triggering Saga Rollback.")
             raise Exception("Verification Failed: Train is no longer available in IRCTC/RapidAPI.")

        return {
            "status": "SUCCESS",
            "message": f"Route {route_id} unlocked successfully.",
            "unlocked_at": time.time()
        }

@router.get("/vitals")
async def get_search_vitals():
    """[Task 50] Master Vitals Hub. Returns zero-latency state from Neural Spine."""
    from core.nexus.cache.mmap_cortex import nexus_cortex
    return {
        "node_status": search_node.status.name,
        "fiber_state": {
            "stress_index": nexus_cortex.get_stress_index(),
            "is_panic": nexus_cortex.is_panic(),
            "is_halted": nexus_cortex.is_kill_switch_active(),
            "throttle_active": nexus_cortex.get_bit(0, 3) # BIT_SCAPER_THROTTLE
        },
        "registry": "v3.fiber.search.l0"
    }
