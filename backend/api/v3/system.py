from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from datetime import datetime
from typing import Dict, Any
import logging
import time

from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState
from core.container import container
from core.nexus.audit.dashboard import nexus_audit
from core.nexus.audit.chaos import nexus_chaos
from services.cache_service import cache_service

logger = logging.getLogger("nexus.system")

router = APIRouter(prefix="/system", tags=["Nexus System"])

@router.get("/health")
async def health_check():
    """[Task 50.3] V3 Master Health Hub."""
    health_status = {
        "status": "V3_OPERATIONAL" if nexus_boot.state == SystemState.READY else nexus_boot.state.value,
        "timestamp": datetime.utcnow().isoformat(),
        "v3_core": True,
        "components": {
             "nexus_fiber": nexus_boot.state.value
        }
    }
    for name, node in nexus_boot.nodes.items():
         health_status["components"][name] = node.status.name
    return health_status

@router.get("/ready")
async def ready_check():
    """Ready check - probe DB/Cache/MQ via IoC containers."""
    if getattr(nexus_boot, 'state', None) in [SystemState.SEVERED, SystemState.DEGRADED]:
        return {
            "status": "ready_ghost_mode", 
            "message": "We are bleeding, but we are alive."
        }
    try:
        # Probe critical services
        db = await container.get("db", timeout=2.0)
        cache = await container.get("cache", timeout=2.0)
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)[:100]}

@router.get("/live")
async def liveness_check():
    """Simple liveness probe."""
    return {"status": "alive", "version": "3.0.0"}

@router.get("/workers")
async def worker_stats():
    """[Task 12.5] Returns per-worker stats from Redis."""
    return await cache_service.get_pattern("gunicorn:worker:*")

@router.get("/services")
async def service_health():
    """Returns the status of all managed IoC services."""
    return container.get_all_status()

@router.get("/vitals")
async def nexus_vitals():
    """[Task 22] Master High-Integrity Dashboard (JSON)."""
    return nexus_audit.get_system_vitals()

@router.get("/triage", response_class=PlainTextResponse)
async def nexus_triage():
    """[Task 22] Human-Readable Health Triage."""
    return nexus_audit.get_triage_report()

# --- CHAOS MESH ---
@router.get("/chaos")
async def list_chaos():
    return nexus_chaos.get_all_traps()

@router.post("/chaos/arm/{name}")
async def arm_chaos(name: str, base: float = 0.1, jitter: float = 0.1, error_rate: float = 0.0):
    nexus_chaos.arm(name, base_delay=base, jitter=jitter, error_rate=error_rate)
    return {"status": "armed", "trap": name}

@router.post("/chaos/disarm/{name}")
async def disarm_chaos(name: str):
    nexus_chaos.disarm(name)
    return {"status": "disarmed", "trap": name}
