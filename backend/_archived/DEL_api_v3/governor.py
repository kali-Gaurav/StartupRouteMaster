from fastapi import APIRouter, Depends
from core.nexus.audit.governor import nexus_governor as governor
from core.nexus.audit.triage import nexus_triage as triage
import time
from utils.responses import v3_response, success_response, error_response

router = APIRouter(prefix="/governor", tags=["Nexus Governor"])

@router.get("/stats")
async def get_governor_stats():
    """Returns real-time 500MB VPS resource telemetry and governor constraints."""
    stats = await governor.get_stats()
    triage_report = await triage.get_deep_diagnostics()
    
    return v3_response({
        "timestamp": time.time(),
        "vps": {
            "cpu_p": stats["cpu_percent"],
            "ram_p": stats["ram_percent"],
            "io_wait_p": stats["io_wait"],
            "redis_p": stats["redis_percent"]
        },
        "governor": {
            "throttle_factor": stats["throttle_factor"],
            "is_throttled": stats["is_throttled"],
            "backoff_factor": triage_report["backoff_factor"]
        },
        "system_status": triage_report["node_status"]
    })

@router.post("/evict")
async def manual_evict():
    """Manual trigger for Redis/L2 Latch clearance."""
    from services.multi_layer_cache import multi_layer_cache
    if multi_layer_cache.redis:
        await multi_layer_cache.redis.delete("rapidapi:*")
        await multi_layer_cache.redis.delete("search_v3:*")
        return success_response("Purged search caches.")
    return error_response("Redis not available.", status_code=503)
