import logging
import sys
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
        title="RouteMaster V2",
        description="Elite High-Performance Railway Routing Protocol",
        version="3.0.0", # FAANG-Grade Refactor Version
        lifespan=lifespan
    )

    # 1. Modular Exceptions
    setup_exception_handlers(app)

    # 2. Unified Middleware Stack [Task 1 & 4 & 5]
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(UnifiedSmartMiddlewareEngine)

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
