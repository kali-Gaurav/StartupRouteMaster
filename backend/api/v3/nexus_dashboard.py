from fastapi import APIRouter, Request, Depends
from typing import Dict, Any
import psutil
import time
import os

from core.nexus.audit.triage import nexus_triage
from core.nexus.audit.chaos import nexus_chaos
from services.scraper_sentinel import scraper_sentinel
from services.multi_layer_cache import multi_layer_cache
from services.delay_predictor import delay_predictor
from services.tatkal_demand_predictor import tatkal_demand_predictor

# [Nexus Integration] Real Telemetry Sources
from core.nexus.financial.rollback import nexus_saga
from core.orchestrator import orchestrator
from core.nexus.bootstrapper import nexus_boot

router = APIRouter(prefix="/nexus", tags=["Nexus Dashboard"])

@router.get("/dashboard/xray")
async def get_nexus_xray(request: Request) -> Dict[str, Any]:
    """
    [Phase 4] The Nexus Health Dashboard Telemetry Endpoint.
    Returns 10 Critical VPS & Engine Metrics for the Cloud Engineer.
    """
    # 1. System Load & Triage Pressure
    mem = psutil.virtual_memory()
    
    # 2. Scraper Sentinel Status
    active_scrapers = len([c for c in scraper_sentinel._contexts if c["in_use"]])
    idle_scrapers = len([c for c in scraper_sentinel._contexts if not c["in_use"]])
    
    # 3. Dynamic Budgeting State
    base_budget = 50000
    current_raptor_budget = max(2000, int(base_budget * (1.0 - nexus_triage.current_backoff)))
    
    # 4. Chaos Mesh Flags
    active_traps = list(nexus_chaos.active_traps.keys()) if hasattr(nexus_chaos, 'active_traps') else []
    
    # 5. ML Models Memory State
    delay_ml_status = "ACTIVE (RAM)" if delay_predictor.model is not None else "DORMANT (DISK)"
    tatkal_ml_status = "ACTIVE (RAM)" if tatkal_demand_predictor.model is not None else "DORMANT (DISK)"
    
    # 6. L1/L2 Cache Latch Health
    try:
        redis_status = "HEALTHY" if multi_layer_cache.redis else "LATCH: DEGRADED (SQLITE)"
    except:
        redis_status = "UNKNOWN"

    # [Task 7] Saga Orchestrator Status
    try:
        orphans = await nexus_saga.list_all_orphaned()
    except:
        orphans = []

    # [Task 8] Routing Engine Real-time Health
    tier_status = orchestrator.engine_registry.get_tier_status()
    
    # [Task 9] Firewall / Penalty Box Status (Redis Keys)
    jailed_ips = 0
    if multi_layer_cache.redis:
        try:
            jailed_keys = await multi_layer_cache.redis.keys("penalty:jail:*")
            jailed_ips = len(jailed_keys)
        except:
             jailed_ips = -1

    # [Task 10] Ghost Mode / Global System State
    ghost_mode = "ACTIVE" if nexus_boot.state.name in ["DEGRADED", "HALTED", "SEVERED"] else "DISABLED"

    return {
        "status": "NEXUS_ONLINE",
        "timestamp": time.time(),
        "metrics": {
            "1_vps_triage_gauge": {
                "system_pressure": round(nexus_triage.current_backoff, 2),
                "ram_used_percentage": mem.percent,
                "ram_free_mb": int(mem.available / (1024 * 1024)),
                "state": "CRITICAL" if nexus_triage.current_backoff > 0.7 else "NOMINAL"
            },
            "2_scraper_sentinel": {
                "active_chromium_contexts": active_scrapers,
                "idle_contexts": idle_scrapers,
                "oom_purge_status": "ARMED" if nexus_triage.current_backoff > 0.7 else "STANDBY"
            },
            "3_raptor_dynamic_budget": {
                "base_nodes": base_budget,
                "current_cap": current_raptor_budget,
                "pruned_nodes": base_budget - current_raptor_budget
            },
            "4_chaos_mesh": {
                "active_faults": active_traps,
                "mesh_state": "ENGAGED" if active_traps else "DISENGAGED"
            },
            "5_cache_integrity": {
                "redis_l2_status": redis_status,
                "l1_memory_fallback": "ACTIVE"
            },
            "6_ml_telemetry": {
                "delay_predictor": delay_ml_status,
                "tatkal_predictor": tatkal_ml_status,
                "lazy_load_latch": "ACTIVE"
            },
            "7_saga_pipeline": {
                "active_tracking": True,
                "pending_or_orphaned_transactions": len(orphans),
                "status": "CONGESTED" if len(orphans) > 5 else "NOMINAL"
            },
            "8_routing_tiers": {
                "tier_1_ultraturbo_online": tier_status.get(1, False),
                "tier_2_turbo_online": tier_status.get(2, False),
                "tier_3_raptor_online": tier_status.get(3, False),
                "fallback_hubs_active": True
            },
            "9_firewall_f2b": {
                "active_jailed_ips": jailed_ips,
                "watch_window_seconds": orchestrator.penalty_box.window_sec,
                "jail_duration_seconds": orchestrator.penalty_box.jail_sec
            },
            "10_ghost_mode": {
                "state": ghost_mode,
                "nexus_bootstrapper_state": nexus_boot.state.name
            }
        }
    }
