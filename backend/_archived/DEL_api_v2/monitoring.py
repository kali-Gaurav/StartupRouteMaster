from fastapi import APIRouter
from utils.external_api_health import api_health
from core.infrastructure.system_monitor import system_monitor
from core.infrastructure.metrics import jit_metrics
from services.multi_layer_cache import multi_layer_cache
from typing import Dict, Any
import json

router = APIRouter(prefix="/monitoring", tags=["Observability & Health"])

@router.get("/external-health")
async def get_external_health():
    """Task 29.5: Get real-time health and latency metrics for external APIs."""
    return api_health.get_status()

@router.get("/system-health")
async def get_system_health():
    """Task 4.7: Expose system metrics API."""
    await system_monitor.update_if_stale()
    return system_monitor.stats

@router.get("/surge")
async def get_surge_status():
    """[Task 24.2] Analysis of system surge levels and request velocity."""
    from core.infrastructure.resource_monitor import resource_monitor
    from core.engines.orchestrator import orchestrator
    
    stats = resource_monitor.get_stats()
    level = resource_monitor.get_surge_level()
    
    return {
        "surge_level": level.name,
        "load_stats": stats,
        "request_velocity": orchestrator.get_rpm(),
        "recommendation": "OBSERVE_ONLY"
    }

@router.get("/dashboard")
async def get_observability_dashboard():
    """
    🛡️ TASK 13: Unified Observability Dashboard.
    Combines System Health, Latency Heatmaps, SLA Tracking, and Worker Stats.
    Provides FAANG-level visibility into system state and bottlenecks.
    """
    await system_monitor.update_if_stale()
    
    # Ensure Redis is loaded
    if not multi_layer_cache.redis:
        from core.infrastructure.container import container
        await container.get("cache")

    heatmaps = {}
    sla_violations = {}
    worker_stats = {}

    if multi_layer_cache.redis:
        # [Task 13.8] Fetch Latency Heatmaps (Histogram Data)
        heatmap_keys = await multi_layer_cache.redis.keys("metrics:heatmap:*")
        for k in heatmap_keys:
            key_str = k.decode() if isinstance(k, bytes) else k
            endpoint = key_str.split(":")[-1]
            # hgetall (returns dict with decode_responses=False logic depends on multi_layer_cache setup)
            # multi_layer_cache.redis uses decode_responses=False by default (see MultiLayerCache.init)
            raw_heatmap = await multi_layer_cache.redis.hgetall(k)
            heatmaps[endpoint] = {k.decode(): int(v.decode()) for k, v in raw_heatmap.items()}
            
        # [Task 13.9] SLA Violations
        sla_keys = await multi_layer_cache.redis.keys("metrics:sla_violations:*")
        for sk in sla_keys:
            key_str = sk.decode() if isinstance(sk, bytes) else sk
            endpoint = key_str.split(":")[-1]
            count = await multi_layer_cache.redis.get(sk)
            sla_violations[endpoint] = int(count.decode()) if count else 0

        # [Task 12.5] Gunicorn Worker Fleet Stats
        worker_keys = await multi_layer_cache.redis.keys("gunicorn:worker:*")
        for wk in worker_keys:
            key_str = wk.decode() if isinstance(wk, bytes) else wk
            worker_id = key_str.split(":")[-1]
            raw_val = await multi_layer_cache.redis.get(wk)
            if raw_val:
                worker_stats[worker_id] = json.loads(raw_val.decode())

    return {
        "status": "HEALTHY" if not jit_metrics.is_overloaded else "OVERLOADED",
        "system_vitals": system_monitor.stats,
        "search_telemetry": jit_metrics.get_report(),
        "performance_dist": heatmaps,
        "sla_compliance": {
            "critical_violations": sla_violations,
            "sla_target_ms": 2000
        },
        "worker_fleet": {
            "count": len(worker_stats),
            "details": worker_stats
        },
        "incidents": {
            "active_alerts": len(getattr(system_monitor, "_alerts", [])),
            "last_incident": "None" # In real app, fetch from audit logs
        }
    }
