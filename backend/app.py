import logging
import sys
import os
import asyncio
import secrets
import time
import anyio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from starlette.types import ASGIApp, Scope, Receive, Send
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

# --- JIT & Profiling Services ---
from services.jit_manager import jit_manager
from core.middleware.traffic_profiler import AsyncTrafficAnalyzer
from core.orchestrator import orchestrator

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
    # 1. Register JIT Nodes
    jit_manager.register_node("DATABASE", [], load_database)
    jit_manager.register_node("CACHE", [], load_cache)
    jit_manager.register_node("GRAPH", ["DATABASE", "CACHE"], load_route_engine)
    jit_manager.register_node("ML_MODELS", ["DATABASE"], load_ml_models)
    
    # 2. Register Background Services with Orchestrator
    from services.feedback_loop import feedback_loop
    from services.behavior_tracker import behavior_tracker
    from database.session import run_pool_scaler, run_connection_reaper, run_ghost_connection_killer
    from core.metrics import run_event_loop_monitor, run_hardware_monitor
    from core.ml_models.loader import model_loader
    from services.multi_layer_cache import multi_layer_cache
    from utils.http_client import HttpClientManager
    
    # Core Infrastructure
    await HttpClientManager.get_session()
    
    # Orchestrate Tasks (Advanced 24/7 Management)
    # Priority 0: Critical Monitors
    orchestrator.register_task("event_loop_monitor", run_event_loop_monitor, priority=0)
    orchestrator.register_task("hardware_monitor", run_hardware_monitor, priority=0)
    
    # Priority 1: Infrastructure Maintenance
    orchestrator.register_task("db_pool_scaler", run_pool_scaler, priority=1)
    orchestrator.register_task("db_conn_reaper", run_connection_reaper, priority=1)
    orchestrator.register_task("db_ghost_killer", run_ghost_connection_killer, priority=1)
    
    # Priority 2: Background Logic & Analytics
    orchestrator.register_task("feedback_punishment", feedback_loop.run_punishment_cycle, priority=2)
    orchestrator.register_task("behavior_cleanup", behavior_tracker.cleanup_idle_states, priority=2)
    orchestrator.register_task("ml_eviction", model_loader.run_eviction_worker, priority=2)
    orchestrator.register_task("trending_analyzer", multi_layer_cache.warmup.run_trending_analyzer, priority=2)
    
    # Start all managed services
    await orchestrator.bootstrap()
    
    # 3. Trigger Foundation Warmup
    asyncio.create_task(jit_manager.ensure_ready("DATABASE"))
    asyncio.create_task(jit_manager.ensure_ready("CACHE"))
    asyncio.create_task(multi_layer_cache.prewarm_top_routes())
    
    logger.info("🚀 RouteMaster V2 Backend Online. Managed via SystemOrchestrator.")
    yield
    
    # Clean Shutdown
    from utils.http_client import HttpClientManager
    await HttpClientManager.close_session()
    await orchestrator.shutdown()
    await multi_layer_cache.aclose()

# --- APP INITIALIZATION ---

app = FastAPI(
    title="RouteMaster V2",
    description="Intelligent, Safe, and Ethical Railway Routing",
    version="2.6.4",
    lifespan=lifespan
)

# --- MIDDLEWARE DEFINITIONS ---

from utils.responses import SafeJSONResponse

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

class ConnectionLimiterMiddleware:
    """
    Subtask 1.14: ASGI Connection Limiter.
    Caps total concurrent HTTP connections to prevent OS descriptor exhaustion.
    """
    def __init__(self, app: ASGIApp, max_connections: int = 1000):
        self.app = app
        self.max_connections = max_connections
        self.active_connections = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        is_priority = any(p in path for p in ["/api/sos", "/api/health", "/api/admin"])
        
        if not is_priority and self.active_connections >= self.max_connections:
            logger.error(f"🚫 Connection Limit Reached ({self.active_connections}). Rejecting {path}")
            response = SafeJSONResponse(
                status_code=503,
                content={
                    "error": True,
                    "message": "System is at peak capacity. Please try again in a few minutes.",
                    "retry_after": 60
                }
            )
            return await response(scope, receive, send)

        self.active_connections += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active_connections = max(0, self.active_connections - 1)

class DynamicBodySizeMiddleware:
    """
    Subtask 1.19: Adaptive Body Size Limits.
    Restricts request body size dynamically based on system load.
    Prevents memory-exhaustion via large payloads during surges.
    """
    def __init__(self, app: ASGIApp, max_size_bytes: int = 1024 * 1024): # 1MB Default
        self.app = app
        self.max_size_bytes = max_size_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from core.metrics import jit_metrics
        path = scope.get("path", "")
        
        # Determine effective limit
        effective_limit = self.max_size_bytes
        if jit_metrics.is_overloaded:
            effective_limit = 10 * 1024 # 10KB during surge
        
        # Check Content-Length header
        headers = dict(scope.get("headers", []))
        content_length = int(headers.get(b"content-length", 0))
        
        if content_length > effective_limit:
            logger.warning(f"🚫 Payload Too Large: {content_length} bytes exceeds limit of {effective_limit} on {path}")
            response = SafeJSONResponse(
                status_code=413,
                content={
                    "error": True,
                    "message": f"Request payload too large for current system load ({effective_limit} bytes max)."
                }
            )
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)

class DropAllMiddleware:
    """
    Subtask 1.17: Emergency Kill Switch.
    Blocks all non-emergency traffic when active.
    Highest priority middleware.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from core.orchestrator import orchestrator
        path = scope.get("path", "")
        
        # 1. Check if kill switch is active
        if await orchestrator.is_kill_switch_active():
            # 2. Allow absolute bypass for emergency services only
            is_emergency = any(p in path for p in ["/api/sos", "/api/health", "/api/admin"])
            
            if not is_emergency:
                response = SafeJSONResponse(
                    status_code=503,
                    content={
                        "error": True,
                        "message": "System is temporarily unavailable due to an emergency lockdown.",
                        "retry_after": 600
                    }
                )
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)

class MaintenanceMiddleware:
    """
    Subtask 1.12: Maintenance Mode.
    Intercepts all requests when system is in maintenance.
    Allows bypass for /api/health and /api/admin.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from core.orchestrator import orchestrator
        path = scope.get("path", "")
        
        # 1. Check if maintenance is active
        if await orchestrator.is_in_maintenance():
            # 2. Allow bypass routes
            is_bypass = any(p in path for p in ["/api/health", "/api/admin", "/api/v2/admin"])
            
            # 3. Allow session-based bypass (active users finish their flow)
            headers = dict(scope.get("headers", []))
            has_session = b"session-id" in headers or b"x-session-id" in headers
            
            if not is_bypass and not has_session:
                response = SafeJSONResponse(
                    status_code=503,
                    content={
                        "error": True,
                        "message": "System is currently under maintenance. We'll be back shortly!",
                        "retry_after": 300
                    }
                )
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)

class ConnectionSheddingMiddleware:
    """
    Subtask 1.7: Connection Shedding.
    Monitors RAM usage and drops non-priority connections if RAM > 90%.
    Ultimate protection against OOM on small VPS.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from core.metrics import jit_metrics
        path = scope.get("path", "")
        
        # Priority bypass
        if any(p in path for p in ["/api/sos", "/api/health", "/api/admin"]):
            return await self.app(scope, receive, send)

        if jit_metrics.ram_usage_percent > 90:
            logger.error(f"🚨 RAM CRITICAL ({jit_metrics.ram_usage_percent}%): Shedding connection to {path}")
            response = SafeJSONResponse(
                status_code=503,
                content={
                    "error": True,
                    "message": "System resource limits reached. Connection shed to prevent crash.",
                    "retry_after": 30
                }
            )
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)

class PriorityQueueMiddleware:
    """
    Subtask 1.6: Priority Queue System.
    Uses a semaphore to limit active concurrent heavy requests.
    Prioritizes emergency (SOS) and health traffic.
    """
    def __init__(self, app: ASGIApp, max_concurrent: int = 20):
        self.app = app
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        # Priority 0: Emergency/Internal
        # Priority 1: Auth/Critical
        # Priority 2: Standard Search/Heavy
        is_priority_0 = any(p in path for p in ["/api/sos", "/api/health", "/api/metrics"])
        
        if is_priority_0:
            # Bypass queue entirely for ultra-priority
            return await self.app(scope, receive, send)

        # Standard requests must acquire semaphore
        try:
            # If loop is laggy, we wait less time for a slot (fail fast)
            from core.metrics import jit_metrics
            wait_timeout = 2.0 if jit_metrics.event_loop_latency_ms > 50 else 5.0
            
            async with asyncio.timeout(wait_timeout):
                async with self.semaphore:
                    return await self.app(scope, receive, send)
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning(f"⏳ Priority Queue: Slot timeout for {path}. System at capacity.")
            response = SafeJSONResponse(
                status_code=503,
                content={
                    "error": True, 
                    "message": "System is at peak capacity. Please retry in a few seconds.",
                    "retry_after": 5
                }
            )
            return await response(scope, receive, send)

class SoftScalingMiddleware:
    """
    Subtask 1.5: Soft Scaling Middleware.
    Sheds load based on real-time VPS CPU/Latency metrics.
    Ensures priority routes (SOS) stay alive while search is throttled.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        from core.metrics import jit_metrics
        path = scope.get("path", "")
        
        # 1. Check for extreme overload
        # If latency > 200ms or CPU > 95%, we drop NON-PRIORITY traffic
        is_priority = any(p in path for p in ["/api/sos", "/api/health", "/api/auth"])
        
        if jit_metrics.cpu_usage_percent > 95 or jit_metrics.event_loop_latency_ms > 200:
            if not is_priority:
                logger.warning(f"🔥 Load Shedding: Dropping request to {path} due to extreme load.")
                response = SafeJSONResponse(
                    status_code=503,
                    content={
                        "error": True, 
                        "message": "Server is under extreme load. Priority given to emergency services.",
                        "retry_after": 10
                    }
                )
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)

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

# 8. Soft Scaling (Absolute Outermost - fast load shedding)
app.add_middleware(SoftScalingMiddleware)

# 9. Priority Queue (Just inside soft scaling)
app.add_middleware(PriorityQueueMiddleware, max_concurrent=5) # Max 5 concurrent heavy requests for testing

# 10. Maintenance Mode (Absolute Outermost)
app.add_middleware(MaintenanceMiddleware)

# 11. Emergency Kill Switch (The Final Gate)
app.add_middleware(DropAllMiddleware)

# 12. Dynamic Body Size (Absolute Outermost)
app.add_middleware(DynamicBodySizeMiddleware)

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

# --- Global Exception Handlers (Subtask 9.4 / 20.7) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Task 20.7: Fallback Safe Mode.
    Catches all unhandled exceptions to prevent process crash.
    """
    error_id = secrets.token_hex(4).upper()
    logger.error(f"🚨 SYSTEM PANIC [{error_id}]: {type(exc).__name__}: {exc}", exc_info=True)
    
    # Check if this is a recurring failure that might require a restart
    # (Future logic: trigger orchestrator.request_restart() if error rate > X)
    
    return SafeJSONResponse(
        status_code=500,
        content={
            "error": True, 
            "message": "RouteMaster Protocol: Safe Mode Active.", 
            "protocol_code": f"ERR_SYSTEM_PANIC_{error_id}",
            "type": type(exc).__name__,
            "recovery_hint": "Neural Link re-establishing. Please retry in 5 seconds."
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return SafeJSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail}
    )

# --- CORE STATUS ENDPOINTS ---

@app.post("/api/admin/kill-switch")
async def toggle_kill_switch(active: bool):
    """Toggle emergency kill switch."""
    await orchestrator.set_kill_switch(active)
    return {"status": "success", "kill_switch_active": active}

@app.post("/api/admin/maintenance")
async def toggle_maintenance(enabled: bool):
    """Toggle system maintenance mode."""
    await orchestrator.set_maintenance_mode(enabled)
    return {"status": "success", "maintenance_mode": enabled}

@app.get("/api/health")
@app.get("/api/health/live")
async def health_check():
    from core.metrics import jit_metrics
    return {
        "status": "online",
        "system": orchestrator.get_health_report(),
        "jit_dag": jit_manager.get_status(),
        "jit_intelligence": jit_metrics.get_report(),
        "timestamp": datetime.utcnow().isoformat()
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
    while time.time() - start < 0.5:
        [math.sqrt(i) for i in range(10000)]
    return {"message": "CPU spike completed"}

@app.post("/api/admin/recycle")
async def recycle_system():
    """Task 20.2: Clean system recycle via watchdog."""
    logger.critical("♻️ SYSTEM RECYCLE REQUESTED. Shutting down worker...")
    # Exit with non-zero to trigger watchdog restart
    os._exit(1)

@app.get("/api/test/panic")
async def trigger_panic():
    """Force an unhandled exception to test the global super-handler."""
    raise RuntimeError("TEST_PANIC_PROTOCOL_V2")

@app.get("/")
async def root():
    return {"message": "RouteMaster V2 API Portal.", "jit": "active"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
