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

# --- JIT & Profiling Services ---
from services.jit_manager import jit_manager
from core.middleware.traffic_profiler import AsyncTrafficAnalyzer

# --- Logging Setup ---
from utils.structured_logging import setup_logging
setup_logging()
logger = logging.getLogger("api-gateway")

# Silence noisy third-party logs
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- JIT NODE LOADERS ---

async def load_database():
    from database.session import init_db
    await init_db()

async def load_cache():
    from services.multi_layer_cache import multi_layer_cache
    await multi_layer_cache.initialize()

async def load_route_engine():
    from core.route_engine import route_engine
    await route_engine._get_current_graph(datetime.utcnow())

async def load_ml_models():
    from core.ml_models.loader import model_loader
    await model_loader.get_model("delay_model")

# --- LIFESPAN ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Register DAG
    jit_manager.register_node("DATABASE", [], load_database)
    jit_manager.register_node("CACHE", [], load_cache)
    jit_manager.register_node("GRAPH", ["DATABASE", "CACHE"], load_route_engine)
    jit_manager.register_node("ML_MODELS", ["DATABASE"], load_ml_models)
    
    # 2. Start Background Services
    from services.feedback_loop import feedback_loop
    from services.behavior_tracker import behavior_tracker
    from services.prediction_hub import prediction_hub
    from database.session import run_pool_scaler, run_connection_reaper
    from core.ml_models.loader import model_loader
    from services.multi_layer_cache import multi_layer_cache
    
    prediction_hub.start()
    app.state.feedback_task = asyncio.create_task(feedback_loop.run_punishment_cycle())
    app.state.behavior_task = asyncio.create_task(behavior_tracker.cleanup_idle_states())
    app.state.pool_scaler_task = asyncio.create_task(run_pool_scaler())
    app.state.reaper_task = asyncio.create_task(run_connection_reaper())
    app.state.ml_eviction_task = asyncio.create_task(model_loader.run_eviction_worker())
    app.state.cache_warmup_task = asyncio.create_task(multi_layer_cache.warmup.run_trending_analyzer())
    
    # 3. Trigger Foundation Warmup
    asyncio.create_task(jit_manager.ensure_ready("DATABASE"))
    asyncio.create_task(jit_manager.ensure_ready("CACHE"))
    asyncio.create_task(multi_layer_cache.prewarm_top_routes())
    
    logger.info("🚀 RouteMaster V2 Backend Online. JIT DAG Active.")
    yield
    
    # Clean Shutdown
    prediction_hub.stop()
    if hasattr(app.state, "feedback_task"): app.state.feedback_task.cancel()
    if hasattr(app.state, "behavior_task"): app.state.behavior_task.cancel()
    if multi_layer_cache.redis: await multi_layer_cache.redis.close()

# --- APP INITIALIZATION ---

app = FastAPI(
    title="RouteMaster V2",
    description="Intelligent, Safe, and Ethical Railway Routing",
    version="2.6.4",
    lifespan=lifespan
)

# --- MIDDLEWARE (Order: Inner to Outer) ---

# GZip
app.add_middleware(GZipMiddleware, minimum_size=500)

# Observability
from core.middleware.observability import ObservabilityMiddleware
app.add_middleware(ObservabilityMiddleware)

# DB Lifecycle
from core.middleware.db_lifecycle import DatabaseLifecycleMiddleware
app.add_middleware(DatabaseLifecycleMiddleware)

# Rate Limiting
from core.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Traffic Profiler (Moved to standard middleware chain)
app.add_middleware(AsyncTrafficAnalyzer)

# CORS (Outer-most)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def unified_jit_middleware(request: Request, call_next):
    """
    Unified JIT Middleware:
    1. Handles path-based eager loading (GRAPH vs DATABASE).
    2. Supports WebSocket upgrade handshakes.
    3. Ensures a response is ALWAYS returned to avoid TaskGroup errors.
    """
    path = request.url.path
    
    # 1. Skip JIT for health, docs, and root
    if "health" in path or path.startswith("/api/docs") or path == "/":
        return await call_next(request)

    # 2. Trigger JIT readiness
    try:
        if path.startswith("/api/search") or path.startswith("/api/v2/search") or "stats" in path:
            await jit_manager.ensure_ready("GRAPH")
        elif path.startswith("/api"):
            await jit_manager.ensure_ready("DATABASE")
            await jit_manager.ensure_ready("CACHE")
            
    except Exception as e:
        logger.error(f"JIT Middleware Error: {e}")
        # Only return JSON if it's NOT a WebSocket attempt
        if request.headers.get("upgrade") != "websocket":
            return JSONResponse(
                status_code=503,
                content={"error": True, "message": "System is still initializing. Please retry in 5 seconds."}
            )

    # 3. Proceed to next handler
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Middleware call_next crash: {e}")
        return JSONResponse(status_code=500, content={"error": True, "message": "Internal processing error."})

# --- STATIC FILES ---
os.makedirs("media/sos", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

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

# --- CORE STATUS ENDPOINTS ---

@app.get("/api/health")
@app.get("/api/health/live")
async def health_check():
    from core.metrics import jit_metrics
    return {
        "status": "online",
        "jit_dag": jit_manager.get_status(),
        "jit_intelligence": jit_metrics.get_report(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/stats")
async def get_stats_proxy():
    """Proxy for monitoring stats to satisfy frontend expectations."""
    from core.metrics import jit_metrics
    return {
        "active_users": 1,
        "total_requests": jit_metrics.predictions_total,
        "performance_score": 98.2,
        "uptime": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    return {"message": "RouteMaster V2 API Portal.", "jit": "active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
