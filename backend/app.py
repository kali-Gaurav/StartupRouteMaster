import logging
import sys
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

# --- Logging Setup ---
from utils.structured_logging import setup_logging
setup_logging()
logger = logging.getLogger("api-gateway")

# Silence noisy third-party logs
logging.getLogger("aiosqlite").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Deferred imports
def get_config():
    from database.config import Config
    return Config

def get_cache():
    from services.multi_layer_cache import multi_layer_cache
    return multi_layer_cache

# --- JUST-IN-TIME (JIT) INITIALIZATION LOGIC ---
app_init_lock = asyncio.Lock()
app_initialized = False
app_init_error = None

async def ensure_system_ready():
    """
    ROOT FIX: All preprocessing starts ONLY when a related task is requested.
    This ensures the backend starts INSTANTLY and never gets stuck in a loop.
    """
    global app_initialized, app_init_error
    if app_initialized:
        return

    async with app_init_lock:
        # Double-check after acquiring lock
        if app_initialized:
            return
            
        logger.info("⚡ JIT: Starting root-level preprocessing (Triggered by request)...")
        app_init_error = None
        
        try:
            # 1. Database Schema Verification (Fix for "no such table: stops")
            from database.session import init_db
            logger.info("🗄️ JIT: Verifying database schemas...")
            await init_db()
            
            # 2. Initialize Cache (Redis/RAM)
            cache = get_cache()
            await cache.initialize()
            logger.info("✅ JIT: Cache Layer Online.")
            
            # 3. Warm up Routing Engine (Loads graph from NPZ/DB)
            from core.route_engine import route_engine
            logger.info("📡 JIT: Warming up routing graph...")
            await route_engine._get_current_graph(datetime.utcnow())
            logger.info("✅ JIT: Routing graph ready.")
            
            app_initialized = True
            logger.info("🏁 JIT: System fully operational.")
        except Exception as e:
            app_init_error = str(e)
            logger.error(f"❌ JIT Initialization failed: {e}")
            # Raise exception so the calling request knows it failed
            raise HTTPException(status_code=503, detail=f"System initialization failed: {app_init_error}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Instant startup lifespan."""
    Config = get_config()
    logger.info(f"🚀 RouteMaster V2 Backend Online (Env: {Config.ENVIRONMENT})...")
    logger.info("💡 Note: Preprocessing is deferred until the first API request.")
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down RouteMaster V2...")
    cache = get_cache()
    if cache.redis:
        await cache.redis.close()

app = FastAPI(
    title="RouteMaster V2",
    description="Intelligent, Safe, and Ethical Railway Routing",
    version="2.5.4",
    lifespan=lifespan
)

# --- MIDDLEWARE ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from core.middleware.rate_limit import RateLimitMiddleware
from core.middleware.observability import ObservabilityMiddleware

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ObservabilityMiddleware)

@app.middleware("http")
async def jit_initialization_middleware(request: Request, call_next):
    """
    Middleware to trigger JIT initialization.
    Exceptions: Root path, Docs, and Health checks.
    """
    path = request.url.path
    is_api = path.startswith("/api")
    is_health = "health" in path
    is_docs = path.startswith("/api/docs") or path.startswith("/api/redoc") or path.startswith("/openapi.json")
    
    if is_api and not is_health and not is_docs:
        await ensure_system_ready()
        
    return await call_next(request)

# --- ROUTER REGISTRATION ---

def register_routers(app: FastAPI):
    from api.v2 import (
        search as search_v2, live, monitoring, user as user_v2, 
        booking as booking_v2, booking_ws, debug, admin, 
        admin_auth, agent, unlock, webhooks, auth_refresh
    )
    
    V2_PREFIX = "/api/v2"
    app.include_router(search_v2.router, prefix=V2_PREFIX)
    app.include_router(live.router, prefix=V2_PREFIX)
    app.include_router(monitoring.router, prefix=V2_PREFIX)
    app.include_router(user_v2.router, prefix=V2_PREFIX)
    app.include_router(booking_v2.router, prefix=V2_PREFIX)
    app.include_router(booking_ws.router, prefix=V2_PREFIX)
    app.include_router(debug.router, prefix=V2_PREFIX)
    app.include_router(admin.router, prefix=V2_PREFIX)
    app.include_router(admin_auth.router, prefix=V2_PREFIX)
    app.include_router(agent.router, prefix=V2_PREFIX)
    app.include_router(unlock.router, prefix=V2_PREFIX)
    app.include_router(webhooks.router, prefix=V2_PREFIX)
    app.include_router(auth_refresh.router, prefix=V2_PREFIX)

    from api import (
        chat, chat_ws, sos, search, bookings, stations,
        payments, auth, users, flow, bank_webhooks,
        admin_refunds, admin_reconciliation, tatkal,
        telegram_bot, vault, status, admin as admin_v1
    )

    V1_PREFIX = "/api"
    app.include_router(status.router, prefix=V1_PREFIX)
    app.include_router(sos.router, prefix=V1_PREFIX)
    app.include_router(chat.router, prefix=V1_PREFIX)
    app.include_router(chat_ws.router, prefix=V1_PREFIX)
    app.include_router(search.router, prefix=V1_PREFIX)
    app.include_router(bookings.router, prefix=V1_PREFIX)
    app.include_router(stations.router, prefix=V1_PREFIX)
    app.include_router(payments.router, prefix=V1_PREFIX)
    app.include_router(auth.router, prefix=V1_PREFIX)
    app.include_router(users.router, prefix=V1_PREFIX)
    app.include_router(flow.router, prefix=V1_PREFIX)
    app.include_router(bank_webhooks.router, prefix=V1_PREFIX)
    app.include_router(admin_refunds.router, prefix=V1_PREFIX)
    app.include_router(admin_reconciliation.router, prefix=V1_PREFIX)
    app.include_router(tatkal.router, prefix=V1_PREFIX)
    app.include_router(telegram_bot.router, prefix=V1_PREFIX)
    app.include_router(vault.router, prefix=V1_PREFIX)
    app.include_router(admin_v1.router, prefix="/api/v1")

register_routers(app)

# --- EXCEPTION HANDLER ---

@app.exception_handler(Exception)
async def unified_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(f"UNHANDLED ERROR: {exc}\n{traceback.format_exc()}")
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
        content={
            "error": True,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "A critical system error occurred.",
            "detail": str(exc) if os.getenv("ENVIRONMENT") == "development" else "Hidden"
        }
    )

# --- CORE STATUS ENDPOINTS ---

@app.get("/health")
@app.get("/api/health")
async def health_check_root():
    cache = get_cache()
    return {
        "status": "healthy" if app_initialized else "initializing",
        "cache": "connected" if (cache.redis and cache._initialized) else "pending/ram",
        "ready": app_initialized,
        "error": app_init_error,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health/live")
async def api_liveness_probe():
    return {"status": "live"}

@app.get("/api/stats")
async def api_status_stats():
    # Only try to load stats if we are initialized, otherwise return empty
    nodes = 0
    if app_initialized:
        from core.route_engine import route_engine
        try:
            nodes = len(route_engine.current_graph.nodes) if route_engine.current_graph else 0
        except Exception: pass

    return {
        "status": "active",
        "graph_nodes": nodes,
        "initialized": app_initialized,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    return {
        "message": "RouteMaster V2 API Online.", 
        "init_status": "complete" if app_initialized else "deferred"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
