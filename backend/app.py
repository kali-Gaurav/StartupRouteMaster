import logging
import sys
import os
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from datetime import datetime

# --- UVLOOP OPTIMIZATION (Task 5) ---
if sys.platform != "win32":
    try:
        import uvloop
        import asyncio
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError: pass

# --- MODULAR CORE ---
from core.lifespan import lifespan
from core.routing import register_routers
from core.exceptions import setup_exception_handlers
from utils.structured_logging import setup_logging

# Initialize Logging
setup_logging()
logger = logging.getLogger("api-gateway")

# --- APP FACTORY ---
def create_app() -> FastAPI:
    """
    Final Refactor: Consolidated Production API Gateway.
    Purged all redundant routes; delegated to modular router registry.
    """
    app = FastAPI(
        title="RouteMaster V3",
        description="Industrial-Grade Railway Search with Sentinel Security & Ledger Governance.",
        version="3.0.0",
        lifespan=lifespan
    )
    
    # [Task 1.10] Nexus Gatekeeper Integration (Global Security Layer)
    from core.nexus.gatekeeper import nexus_gatekeeper
    app.router.dependencies.append(Depends(nexus_gatekeeper))

    # 1. Modular Exceptions
    setup_exception_handlers(app)

    # 2. Unified Middleware Stack [Task 1 & 4 & 5]
    from core.middleware import setup_middleware
    setup_middleware(app)

    # 3. Modular Routing (Registers V1, V2, V3 and System routes)
    register_routers(app)
    
    # [Nexus 100: Phase 4] Legacy Dashboard Mount (Keep for UI compatibility)
    from api.v3.nexus_dashboard import router as nexus_dashboard_router
    app.include_router(nexus_dashboard_router)

    # 4. Static Files (Standard Mount)
    os.makedirs("media/sos", exist_ok=True)
    app.mount("/media", StaticFiles(directory="media"), name="media")

    return app

app = create_app()

# --- ELITE ROOT HANDLERS ---
@app.get("/", tags=["Health"])
async def root():
    """Elite System Entry Point."""
    return {
        "message": "RouteMaster Elite Protocol Online.", 
        "engine": "nexus_spine_v3",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/ping", tags=["Health"])
async def ping():
    return {"status": "pong", "timestamp": datetime.utcnow().isoformat()}

# --- FRONTEND COMPATIBILITY ROUTES (Root & API Aliases) ---
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def api_health():
    """Consolidated Health for Frontend and Integration Tests."""
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.state import SystemState
    return {
        "status": "V3_OPERATIONAL" if nexus_boot.state == SystemState.READY else nexus_boot.state.value,
        "timestamp": datetime.utcnow().isoformat(),
        "v3_core": True,
        "maintenance": False,
        "surge_level": "Normal",
        "components": {
            "nexus": "HEALTHY",
            "fiber": "CONNECTED"
        }
    }

@app.get("/health/live", tags=["Health"])
@app.get("/api/health/live", tags=["Health"])
async def api_health_live():
    """Liveness probe alias."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health/ready", tags=["Health"])
@app.get("/api/health/ready", tags=["Health"])
async def api_health_ready():
    """Readiness probe alias."""
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.state import SystemState
    return {
        "status": "ready" if nexus_boot.state == SystemState.READY else "degraded",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/stats", tags=["Health"])
@app.get("/api/stats", tags=["Health"])
async def api_stats():
    """Resource telemetry for the frontend dashboard."""
    from core.nexus.audit.governor import nexus_governor
    from core.nexus.telemetry import nexus_telemetry
    
    gov_stats = await nexus_governor.get_stats()
    telemetry_metrics = await nexus_telemetry.get_metrics()

    return {
        "cpu": gov_stats.get("cpu_percent", 0),
        "ram": gov_stats.get("ram_percent", 0),
        "latency_ms": telemetry_metrics.get("avg_latency_ms", 0),
        "requests_per_sec": telemetry_metrics.get("requests_per_sec", 0)
    }

# --- PRODUCTION RUNNER ---
if __name__ == "__main__":
    import uvicorn
    # Use standard host setting for cloud compatibility (Railway/GCR)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
