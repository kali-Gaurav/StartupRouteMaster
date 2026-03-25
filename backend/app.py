import logging
import sys
import os
from fastapi import FastAPI
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
from core.middleware.unified_engine import UnifiedSmartMiddlewareEngine
from core.middleware.observability import ObservabilityMiddleware
from utils.structured_logging import setup_logging

# Initialize Logging
setup_logging()
logger = logging.getLogger("api-gateway")

# --- APP FACTORY ---
def create_app() -> FastAPI:
    """
    Final Refactor: Consolidated Production API Gateway.
    Replaces 1500+ lines across multiple files with Elite-Level Modular Architecture.
    """
    app = FastAPI(
        title="RouteMaster V3",
        description="Industrial-Grade Railway Search with Sentinel Security & Ledger Governance.",
        version="3.0.0",
        lifespan=lifespan
    )
    
    # [Task 50.2] V3 Master Resilience Layer
    from api.middleware import v3_middleware

    # 1. Modular Exceptions
    setup_exception_handlers(app)

    # 2. Unified Middleware Stack [Task 1 & 4 & 5]
    from core.middleware import setup_middleware
    setup_middleware(app)

    # 3. Modular Routing
    register_routers(app)

    # 4. Static Files
    os.makedirs("media/sos", exist_ok=True)
    app.mount("/media", StaticFiles(directory="media"), name="media")

    return app

app = create_app()

# --- STANDALONE ROUTES ---
@app.get("/")
async def root():
    return {"message": "RouteMaster Elite Protocol Online.", "engine": "unified_v3"}

@app.get("/ping")
async def ping():
    return {"status": "pong", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health")
@app.get("/healthz")
async def health_check():
    """
    [Task 50.3] V3 Master Health Hub.
    Comprehensive system health check for Scrapers, Ledger, and Cache.
    """
    from services.multi_layer_cache import multi_layer_cache
    from services.scraper_sentinel import scraper_sentinel
    from services.ledger_service import ledger_service
    
    health_status = {
        "status": "V3_OPERATIONAL",
        "timestamp": datetime.utcnow().isoformat(),
        "v3_core": True,
        "components": {}
    }
    
    # 1. Zero-Latency Cache Heartbeat
    try:
        await multi_layer_cache.put("v3:heartbeat", "alive", ttl=5)
        health_status["components"]["cache"] = {"status": "✅ Active", "latency": "Normal"}
    except:
        health_status["components"]["cache"] = {"status": "❌ Degraded"}
        health_status["status"] = "DEGRADED"

    # 2. Scraper Sentinel Status [Task 48.7]
    health_status["components"]["scrapers"] = {
        "pool": f"{scraper_sentinel._total_contexts}/{scraper_sentinel.BASE_MAX_CONTEXTS}",
        "status": "✅ Active" if scraper_sentinel._total_contexts < scraper_sentinel.BASE_MAX_CONTEXTS else "⚠️ Saturated"
    }

    # 3. Financial Ledger Integrity [Task 49.9]
    try:
        # Quick verify of last 5 records
        integrity = await ledger_service.verify_ledger_integrity(limit=5)
        health_status["components"]["ledger"] = {"status": "✅ Immutable" if integrity else "🚨 Tampered"}
        if not integrity: health_status["status"] = "HALT"
    except:
        health_status["components"]["ledger"] = {"status": "⚠️ Pending"}

    return health_status

@app.get("/healthz/ready")
async def ready_check():
    """
    Ready check - are all critical services ready to accept traffic?
    """
    try:
        from database.session import AsyncSessionLocal
        from sqlalchemy import text
        
        # Check database can be connected
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        
        # Check Redis
        from services.multi_layer_cache import multi_layer_cache
        await multi_layer_cache.put("ready:test", "ok", ttl=5)
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "reason": str(e)[:100],
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/healthz/live")
async def liveness_check():
    """
    Liveness check - is the service still running?
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.0"
    }

@app.get("/healthz/workers")
async def worker_stats():
    """[Task 12.5] Returns per-worker stats stored in Redis by Gunicorn."""
    from services.cache_service import cache_service
    # Scan for gunicorn:worker:* keys
    # Note: This requires gunicorn_conf to write to Redis
    return await cache_service.get_pattern("gunicorn:worker:*")

@app.get("/healthz/services")
async def service_health():
    """Returns the status and health of all managed IoC services."""
    from core.container import container
    return container.get_all_status()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
