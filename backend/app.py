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
    from core.metrics import run_event_loop_monitor, run_hardware_monitor
    from core.ml_models.loader import model_loader

    from services.multi_layer_cache import multi_layer_cache
    from utils.http_client import HttpClientManager
    
    # 0. Global Http Client
    await HttpClientManager.get_session()
    
    prediction_hub.start()
    app.state.feedback_task = asyncio.create_task(feedback_loop.run_punishment_cycle())
    app.state.behavior_task = asyncio.create_task(behavior_tracker.cleanup_idle_states())
    app.state.pool_scaler_task = asyncio.create_task(run_pool_scaler())
    app.state.reaper_task = asyncio.create_task(run_connection_reaper())
    app.state.event_loop_task = asyncio.create_task(run_event_loop_monitor())
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
    from utils.http_client import HttpClientManager
    await HttpClientManager.close_session()
    
    if hasattr(app.state, "feedback_task"): app.state.feedback_task.cancel()
    if hasattr(app.state, "behavior_task"): app.state.behavior_task.cancel()
    await multi_layer_cache.aclose()

# --- APP INITIALIZATION ---

app = FastAPI(
    title="RouteMaster V2",
    description="Intelligent, Safe, and Ethical Railway Routing",
    version="2.6.4",
    lifespan=lifespan
)

# --- MIDDLEWARE DEFINITIONS ---

class ResilientGZipMiddleware:
    """Wrapper around GZipMiddleware to catch disconnected client errors."""
    def __init__(self, app, minimum_size=500):
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)
    async def __call__(self, scope, receive, send):
        try:
            await self.gzip(scope, receive, send)
        except (anyio.EndOfResource, RuntimeError, ConnectionResetError) as e:
            # Client disconnected during compression/stream
            logger.debug(f"GZip: Client disconnected early: {e}")
        except Exception as e:
            logger.error(f"GZip Middleware Error: {e}")
            raise e

class RoutingCircuitBreaker:
    """Proactive circuit breaker for heavy search routes."""
    def __init__(self, failure_threshold=3, recovery_timeout=10):
        self.failures = 0
        self.last_failure_time = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.is_open = False

    def check(self):
        if self.is_open:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("🔧 Routing Circuit Breaker: Attempting recovery (HALF-OPEN)")
                self.is_open = False
                self.failures = 0
                return True
            return False
        return True

    def report_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            logger.error(f"🚨 Routing Circuit Breaker: TRIPPED after {self.failures} failures.")
            self.is_open = True

    def report_success(self):
        if self.failures > 0:
            self.failures = max(0, self.failures - 1)

routing_breaker = RoutingCircuitBreaker()

class UnifiedJITMiddleware:
    """
    Native ASGI JIT Middleware:
    1. Handles path-based eager loading (GRAPH vs DATABASE).
    2. Returns 503 if components are still initializing.
    3. [1.11] Localized circuit breaker for heavy routes.
    Eliminates BaseHTTPMiddleware overhead to prevent 'No response returned' errors.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        try:
            path = scope.get("path", "")
            is_heavy = path.startswith(("/api/search", "/api/v2/search"))
            
            # 1. Skip JIT for health, docs, and root
            if "health" in path or path.startswith("/api/docs") or path == "/":
                return await self.app(scope, receive, send)

            # [1.11] Circuit Breaker Check
            if is_heavy and not routing_breaker.check():
                response = SafeJSONResponse(
                    status_code=503,
                    content={"error": True, "message": "Search system is temporarily overloaded. Please try again in a minute."}
                )
                return await response(scope, receive, send)

            # 2. Trigger JIT readiness
            try:
                if is_heavy or "stats" in path:
                    await jit_manager.ensure_ready("GRAPH")
                elif path.startswith("/api"):
                    await jit_manager.ensure_ready("DATABASE")
                    await jit_manager.ensure_ready("CACHE")
                    
            except Exception as e:
                logger.error(f"JIT Initialization Delay: {e}")
                
                headers = dict(scope.get("headers", []))
                is_websocket = headers.get(b"upgrade") == b"websocket"
                
                if not is_websocket:
                    response = SafeJSONResponse(
                        status_code=503,
                        content={"error": True, "message": "System components are initializing. Please retry in a few seconds.", "retry_after": 5}
                    )
                    return await response(scope, receive, send)
                else:
                    response = SafeJSONResponse(
                        status_code=503,
                        content={"error": True, "message": "WebSocket failed: System initializing."}
                    )
                    return await response(scope, receive, send)

            # 3. Proceed to next handler with monitoring
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    status = message.get("status", 0)
                    if is_heavy:
                        if status >= 500:
                            routing_breaker.report_failure()
                        elif status < 400:
                            routing_breaker.report_success()
                await send(message)

            return await self.app(scope, receive, send_wrapper)
            
        except Exception as exc:
            if is_heavy: routing_breaker.report_failure()
            logger.error(f"CRITICAL: JIT Middleware Crash: {exc}", exc_info=True)
            response = SafeJSONResponse(
                status_code=500,
                content={"error": True, "message": "Internal Middleware Error", "detail": str(exc)}
            )
            return await response(scope, receive, send)

# --- MIDDLEWARE REGISTRATION (Order: Inner to Outer) ---

# 1. GZip (Innermost)
app.add_middleware(ResilientGZipMiddleware, minimum_size=500)

# 2. DB Lifecycle
from core.middleware.db_lifecycle import DatabaseLifecycleMiddleware
app.add_middleware(DatabaseLifecycleMiddleware)

# 3. Rate Limiting
from core.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# 4. Traffic Profiler
app.add_middleware(AsyncTrafficAnalyzer)

# 5. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. Unified JIT
app.add_middleware(UnifiedJITMiddleware)

# 7. Observability (Outermost - RID Context is set here)
from core.middleware.observability import ObservabilityMiddleware
app.add_middleware(ObservabilityMiddleware)

# --- STATIC FILES ---
os.makedirs("media/sos", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

# --- ROUTER REGISTRATION ---

def register_routers(app: FastAPI):
    from api.v2 import (
        search as search_v2, live, monitoring, user as user_v2, 
        booking as booking_v2, booking_ws, debug, admin, 
        admin_auth, agent, unlock, webhooks, auth_refresh,
        sessions
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
    app.include_router(sessions.router, prefix=V2_PREFIX)

    from api import (
        chat, chat_ws, sos, search, bookings, stations,
        payments, auth, users, flow, bank_webhooks,
        admin_refunds, admin_reconciliation, tatkal,
        telegram_bot, vault, status, admin as admin_v1,
        integrated_search
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
    app.include_router(integrated_search.router, prefix=V1_PREFIX)
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

@app.get("/api/health/latency")
async def get_api_latency_health():
    """[2.15] System Health dashboard for API latency."""
    from utils.external_api_health import rapid_api_health, rappid_health
    return {
        "rapid_api": await rapid_api_health.get_status(),
        "rappid_in": await rappid_health.get_status(),
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

@app.get("/api/test/mem-spike")
async def mem_spike():
    """Simulate a memory spike to test Hardware Monitor."""
    import gc
    # Allocate ~100MB of dummy data
    spike_list = []
    for _ in range(10):
        spike_list.append(" " * (10 * 1024 * 1024))
    
    # Hold it for 2 seconds then release
    await asyncio.sleep(2)
    del spike_list
    gc.collect()
    return {"message": "Memory spike completed"}

@app.get("/api/test/cpu-spike")
async def cpu_spike():
    """Simulate a thread-blocking CPU task to test Event Loop Monitor."""
    import math
    import time
    start = time.time()
    # Synchronous block for ~500ms
    while time.time() - start < 0.5:
        [math.sqrt(i) for i in range(10000)]
    return {"message": "CPU spike completed"}

@app.get("/")
async def root():
    return {"message": "RouteMaster V2 API Portal.", "jit": "active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
