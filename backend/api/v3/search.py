from core.nexus.search.node import search_node
import asyncio
import json
import uuid
import logging
import time
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.nexus.search.gate import nexus_latency_gate
from core.auth.integrity import sign_result_payload
from core.nexus.gatekeeper import nexus_gatekeeper
from core.nexus.search.interceptor import nexus_interceptor
from core.nexus.search.sorter import nexus_sorter
from core.nexus.rl.reconciler import rl_reconciler
from core.nexus.synapse import CerebralCache, SynapseOptimizer
from services.search_service import SearchService
from utils.responses import success_response, error_response, v3_response
from database.session import get_db
from core.nexus.audit.chaos import chaos_trap

logger = logging.getLogger("api.v3.search")
router = APIRouter(prefix="/search", tags=["Nexus V3 Elite Search"])

@router.get("/unified")
@chaos_trap("search_unified")
async def unified_nexus_search(
    request: Request,
    background_tasks: BackgroundTasks,
    source: str = Query(..., min_length=2, max_length=10),
    destination: str = Query(..., min_length=2, max_length=10),
    date: str = Query(..., description="YYYY-MM-DD"),
    persona: str = Query("ECONOMY", description="ECONOMY, BUSINESS, EMERGENCY"),
    tier: str = Query("BASIC", description="BASIC (Free), PRO (Standard), ELITE (Premium)"),
    budget: Optional[str] = Query(None),
    bypass_cache: bool = Query(False, description="Force deep graph search"),
    engine_model: Optional[str] = Query(None, description="RAPTOR, TURBO, ENSEMBLE"),
    db: Session = Depends(get_db)
):
    """
    [Task 12] Elite V3 Fiber Search Orchestrator.
    Flow: Gatekeeper -> Nexus Gate (Cache) -> V3 Engine (Graph) -> RL Pricing -> Audit.
    Tiers: 
      - BASIC: Fast, Direct, Free Engines only.
      - PRO: Multi-modal, Safety Scoring, 3-Transfer limit.
      - ELITE: Deep Search (RAPTOR), Real-time verification, 5-Transfer limit.
    """
    start_ts = time.perf_counter()
    
    # Map tier to DiscoveryModel string for backend
    tier_map = {
        "BASIC": "BACKBONE",
        "PRO": "MULTIMODAL",
        "ELITE": "OMNISCIENT"
    }
    active_tier = tier_map.get(tier.upper(), "BACKBONE")
    
    # [Task 45.1] Project Sentinel S1: Identity Fingerprinting
    from services.identity_service import IdentityService
    identity_svc = IdentityService(db)
    fingerprint = await identity_svc.get_or_create_fingerprint(request)
    
    if fingerprint.risk_score > 0.8:
        logger.warning(f"🚫 [SENTINEL] Search blocked for high-risk device: {fingerprint.fingerprint_hash[:10]}")
        return error_response("Access restricted due to suspicious activity.", error_code="FRAUD_LIMIT", status_code=403)

    # 0. High-Integrity Sanitization [Task 13]
    from utils.security import sanitize_string, mask_result_by_tier
    source = sanitize_string(source, length_limit=10).upper()
    destination = sanitize_string(destination, length_limit=10).upper()
    
    # 0.1 Geo-location Capture [Task 14]
    from utils.geo_utils import get_state_from_ip
    client = request.client
    client_ip = request.headers.get("x-track-ip") or (client.host if client else "unknown")
    geo_state = get_state_from_ip(client_ip)
    
    # Use budget if persona is default or budget is provided
    active_persona = (budget or persona).upper()

    # 1. Nexus Fiber Interceptor (Task 18)
    from core.nexus.search.interceptor import NexusInterceptorDecision
    decision = NexusInterceptorDecision(allowed=True, code="INFRA_FAIL_OPEN")
    
    try:
        decision = await nexus_interceptor.intercept(request, source, destination)
        if not decision.allowed:
            return v3_response(
                data=None,
                status="HALT",
                metadata={
                    "code": decision.code,
                    "message": decision.message,
                    "geo_state": geo_state,
                    "interceptor": decision.metadata
                },
                status_code=403
            )
    except Exception as e:
        logger.error(f"⚠️ [RESILIENCE] Interceptor Failure: {e}. Failing Open to Search Engine.")

    # 1.1 Fast-Path Cache Check (Latency Gate)
    try:
        if not bypass_cache:
            cached_results = await nexus_latency_gate.get_cached_search(source, destination, date, active_persona)
            if cached_results:
                # [Industrial Rigor] Apply Tiered Masking
                masked_results = [mask_result_by_tier(j, tier) for j in cached_results]
                
                nonce = str(uuid.uuid4())[:8]
                ts = int(time.time())
                target_user_id = fingerprint.user_id or fingerprint.fingerprint_hash
                sig = sign_result_payload(masked_results, target_user_id, nonce, ts)
                
                return v3_response(
                    data={"journeys": masked_results},
                    metadata={
                        "nonce": nonce,
                        "ts": ts,
                        "fingerprint": fingerprint.fingerprint_hash,
                        "integrity_sig": sig,
                        "cache_hit": "L2_LATENCY_GATE"
                    }
                )
    except Exception as e:
        logger.error(f"⚠️ [RESILIENCE] Latency Gate Failure: {e}. Proceeding to primary engine.")

    # 1.5 [L0] CerebralCache — in-process LRU hit (microsecond response)
    cached_segment = CerebralCache.get_segment(source, destination, date)
    if cached_segment and not bypass_cache:
        logger.info(f"🧠 [SYNAPSE:L0] CerebralCache HIT for {source}->{destination}")
        return v3_response(
            data={"journeys": cached_segment},
            metadata={"cache": "L0_CEREBRAL_HIT", "engine": "synapse_l0"}
        )

    # 2. Unified Search Logic (Tiers 0-3 + Hydration + Verification)
    search_svc = SearchService(db)
    
    try:
        from core.metrics import jit_metrics
        # [Elite] Deep verification needs more time; BASIC/PRO can stay tight
        base_timeout = 300.0 if active_tier == "OMNISCIENT" else 60.0
        adaptive_timeout = jit_metrics.get_adaptive_timeout(base_timeout=base_timeout)
        
        # Ensure a floor for ELITE searches so they don't get throttled too hard
        if active_tier == "OMNISCIENT":
            adaptive_timeout = max(adaptive_timeout, 120.0)
            
        # Execute unified search (Returns hydrated/verified routes)
        v2_result = await asyncio.wait_for(
            search_svc.search_routes(
                source=source,
                destination=destination,
                travel_date=date,
                budget_category=active_persona,
                client_ip=client_ip,
                geo_state=geo_state,
                request=request,
                permitted_engines=[engine_model] if engine_model and engine_model != "ENSEMBLE" else None,
                discovery_model=active_tier
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
        from core.resource_monitor import resource_monitor
        mock_state = np.array([0.5, 0.2, 0.8, 0.3])
        pricing_multiplier = rl_reconciler.get_optimal_multiplier(mock_state)
        
        # 4.5 [SYNAPSE] Intelligent Pruning under load
        resource_budget = resource_monitor.get_resource_budget()
        raw_journeys = SynapseOptimizer.apply_intelligent_pruning(raw_journeys, resource_budget)
        
        # 5. Elite Sorter (Persona-Aware Polarity)
        journey_payloads = []
        for journey in raw_journeys:
            if isinstance(journey, dict):
                journey_payloads.append(journey)
            elif hasattr(journey, "to_dict"):
                journey_payloads.append(journey.to_dict())
            else:
                journey_payloads.append(dict(vars(journey)))

        sorted_results = nexus_sorter.sort_results(journey_payloads, persona=active_persona)
        
        # [Industrial Rigor] Apply Tiered Masking before commit/response
        masked_results = [mask_result_by_tier(j, tier) for j in sorted_results]
        
        # Commit to Latency Gate + CerebralCache for next hits
        await nexus_latency_gate.commit_search(source, destination, date, masked_results, active_persona)
        CerebralCache.set_segment(source, destination, date, masked_results)
        
        # 6. Final V3 Fiber Construction
        from core.nexus.audit.triage import nexus_triage
        backoff = nexus_triage.current_backoff
        search_mode = "DEEP" if backoff < 0.3 else ("ADAPTIVE" if backoff < 0.8 else "SURVIVAL")
        
        # [Point 15.1] Background Intelligence Logging
        from services.intelligence_service import IntelligenceService
        intel_svc = IntelligenceService(db)
        background_tasks.add_task(intel_svc.log_search_served, v2_result.get("session_id"), sorted_results)

        latency_ms = (time.perf_counter() - start_ts) * 1000
        nonce = str(uuid.uuid4())[:8]
        
        final_response_data = {
            "journeys": masked_results,
            "grouped_journeys": v2_result.get("data", {}).get("grouped_journeys", {}),
            "pagination": v2_result.get("data", {}).get("pagination", {})
        }

        # [Industrial Rigor 2.0] Sign with context (Replay Protection)
        target_user_id = fingerprint.user_id or fingerprint.fingerprint_hash
        sig = sign_result_payload(final_response_data, target_user_id, nonce)
        
        return v3_response(
            data=final_response_data,
            status=search_mode,
            metadata={
                "engine": f"nexus_fiber_v3:{search_mode.lower()}",
                "latency_ms": f"{latency_ms:.2f}",
                "interceptor": decision.metadata,
                "geo_state": geo_state,
                "pricing_surge": f"{pricing_multiplier:.2f}x",
                "session_id": v2_result.get("session_id"),
                "nonce": nonce,
                "integrity_sig": sig
            }
        )

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

@router.post("/feedback")
async def record_search_feedback(
    journey_id: str = Query(...),
    action: str = Query("clicked"), # clicked, closed
    db: Session = Depends(get_db)
):
    """[Point 15.2] User Intent Feedback."""
    from services.intelligence_service import IntelligenceService
    intel_svc = IntelligenceService(db)
    await intel_svc.record_conversion(journey_id, action)
    return {"status": "SUCCESS"}


@router.get("/stream")
async def stream_search_sse(
    request: Request,
    source: str = Query(..., min_length=2, max_length=10),
    destination: str = Query(..., min_length=2, max_length=10),
    date: str = Query(..., description="YYYY-MM-DD"),
    persona: str = Query("ECONOMY"),
    db: Session = Depends(get_db)
):
    """
    [Point 18 & 30] Zero-Block Streaming Search via Server-Sent Events.
    Frontend connects once — results progressively stream in.
    """
    from utils.security import sanitize_string
    source = sanitize_string(source, length_limit=10).upper()
    destination = sanitize_string(destination, length_limit=10).upper()

    search_svc = SearchService(db)

    async def event_generator():
        ended = False
        try:
            # Heartbeat immediately so browser doesn't show a blank loader
            yield b"data: {\"chunk\": \"HEARTBEAT\", \"status\": \"SEARCHING\"}\n\n"
            async for chunk in search_svc.stream_routes(
                source=source,
                destination=destination,
                travel_date=date,
                budget_category=persona,
                request=request
            ):
                yield chunk
            ended = True
        except Exception as e:
            logger.exception("Stream search generator failed")
            error_payload = {"chunk": "ERROR", "message": str(e)}
            yield b"data: " + json.dumps(error_payload).encode("utf-8") + b"\n\n"
        finally:
            if not ended:
                yield b"event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering
            "Access-Control-Allow-Origin": "*"
        }
    )
