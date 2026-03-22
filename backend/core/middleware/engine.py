import asyncio
import time
import logging
import os
import secrets
from enum import Enum, IntEnum
from typing import Dict, Any, Optional, List, Set
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

from core.system_monitor import system_monitor, SystemState
from services.jit_manager import jit_manager
from core.metrics import jit_metrics
from utils.responses import SafeJSONResponse
from core.middleware.control import TokenBucket, TrafficPredictor, register_middleware

logger = logging.getLogger("routemaster.middleware.engine")

# Task 1 & 18 Constants & Enums
class PriorityLevel(IntEnum):
    ESSENTIAL = 3  # SOS, Health, Admin
    HIGH = 2       # Auth, Profile
    NORMAL = 1     # Basic API
    LOW = 0        # Analytics, Scrapers

class RouteCategory(Enum):
    SYSTEM = "system"
    AUTH = "auth"
    DATA_LIGHT = "data.light"
    DATA_HEAVY = "data.heavy"
    ANALYTICS = "analytics"

# Task 3.3: Request Weight System
ROUTE_WEIGHTS = {
    RouteCategory.SYSTEM: 1.0,
    RouteCategory.AUTH: 2.0,
    RouteCategory.DATA_LIGHT: 5.0,
    RouteCategory.DATA_HEAVY: 15.0,
    RouteCategory.ANALYTICS: 10.0
}

class PriorityRouter:
    """Task 1.6: Formal Priority Routing Table."""
    def __init__(self):
        # (Path Prefix, Priority, Category)
        self.rules = [
            ("/api/sos", PriorityLevel.ESSENTIAL, RouteCategory.SYSTEM),
            ("/api/health", PriorityLevel.ESSENTIAL, RouteCategory.SYSTEM),
            ("/ping", PriorityLevel.ESSENTIAL, RouteCategory.SYSTEM),
            ("/api/auth", PriorityLevel.HIGH, RouteCategory.AUTH),
            ("/api/user", PriorityLevel.HIGH, RouteCategory.AUTH),
            ("/api/search", PriorityLevel.NORMAL, RouteCategory.DATA_HEAVY),
            ("/api/v2/search", PriorityLevel.NORMAL, RouteCategory.DATA_HEAVY),
            ("/api/integrated_search", PriorityLevel.NORMAL, RouteCategory.DATA_HEAVY),
            ("/api/analytics", PriorityLevel.LOW, RouteCategory.ANALYTICS),
            ("/api/admin", PriorityLevel.ESSENTIAL, RouteCategory.SYSTEM),
        ]

    def classify(self, path: str, method: str) -> (PriorityLevel, RouteCategory):
        for prefix, priority, category in self.rules:
            if path.startswith(prefix):
                return priority, category
        
        # Default for APIs
        if path.startswith("/api"):
            return PriorityLevel.NORMAL, RouteCategory.DATA_LIGHT
        return PriorityLevel.LOW, RouteCategory.SYSTEM

priority_router = PriorityRouter()

class ThrottlingPolicy:
    """Task 1.8: Dynamic Throttling Policy Matrix."""
    @staticmethod
    def get_limits(state: SystemState, priority: PriorityLevel) -> Dict[str, Any]:
        # (Limit Multiplier, Timeout Multiplier)
        matrix = {
            SystemState.NORMAL:    {PriorityLevel.LOW: (1.0, 1.0), PriorityLevel.NORMAL: (1.0, 1.0), PriorityLevel.HIGH: (1.0, 1.0)},
            SystemState.WARNING:   {PriorityLevel.LOW: (0.5, 1.5), PriorityLevel.NORMAL: (0.8, 1.2), PriorityLevel.HIGH: (1.0, 1.0)},
            SystemState.CRITICAL:  {PriorityLevel.LOW: (0.0, 2.0), PriorityLevel.NORMAL: (0.3, 1.5), PriorityLevel.HIGH: (0.8, 1.2)},
            SystemState.EMERGENCY: {PriorityLevel.LOW: (0.0, 3.0), PriorityLevel.NORMAL: (0.0, 2.0), PriorityLevel.HIGH: (0.5, 1.5)},
        }
        
        # Override for Essential
        if priority == PriorityLevel.ESSENTIAL:
            return {"multiplier": 1.0, "timeout_scale": 1.0, "shed": False}
            
        policy = matrix.get(state, matrix[SystemState.NORMAL]).get(priority, (1.0, 1.0))
        return {
            "multiplier": policy[0],
            "timeout_scale": policy[1],
            "shed": policy[0] == 0.0
        }

class SmartMiddleware:
    """
    TASK 1: Unified Smart Middleware Engine.
    Consolidates 16+ redundant middlewares into a single intelligent ASGI pipeline.
    Optimized for performance, maintainability, and predictive scaling.
    """
    def __init__(
        self, 
        app: ASGIApp, 
        max_connections: int = 500, 
        max_concurrent_heavy: int = 20,
        base_timeout: float = 30.0
    ):
        self.app = app
        self.max_connections = max_connections
        self.active_connections = 0
        self.heavy_semaphore = asyncio.Semaphore(max_concurrent_heavy)
        self.base_timeout = base_timeout
        self.origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        
        # Task 3: Adaptive Control Components
        self.bucket = TokenBucket(capacity=200, refill_rate=100)
        self.predictor = TrafficPredictor(alpha=0.3)
        register_middleware(self)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" and scope["type"] != "websocket":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        method = scope.get("method", "")
        headers = dict(scope.get("headers", []))
        
        # 1. EARLY EXIT & FAST PATHS
        # ---------------------------
        # Skip heavy logic for health checks, docs, etc.
        is_essential = any(p in path for p in ["/api/sos", "/api/health", "/api/admin", "/ping"])
        is_search = path.startswith(("/api/search", "/api/v2/search", "/api/integrated_search"))
        is_heavy = is_search or "/api/analytics" in path
        
        # Fast-Path for OPTIONS (CORS preflight)
        if method == "OPTIONS":
            return await self.handle_options(scope, receive, send)

        # Activity Reporting
        from core.orchestrator import orchestrator
        orchestrator.report_request()
        
        try:
            # 2. EMERGENCY & MAINTENANCE LAYERS
            # ----------------------------------
            await system_monitor.update_if_stale()
            sys_state = system_monitor.current_state # Task 4: Centralized state
            
            # Task 1.6 & 1.7: Classification
            priority, category = priority_router.classify(path, method)
            policy = ThrottlingPolicy.get_limits(sys_state, priority)

            # Task 3.4: Predictive Telemetry
            self.predictor.report_request()
            
            # Task 3.2: Token Bucket Consumption (Adaptive Load Control)
            weight = ROUTE_WEIGHTS.get(category, 1.0)
            
            # SLA/Priority Tiering Adjustment [Task 3.7]
            # In a real system, we'd check headers for API keys/tiers.
            if priority >= PriorityLevel.HIGH:
                 weight *= 0.5 # High priority is "cheaper" to processing
                 
            allowed = await self.bucket.consume(weight)

            # Decision Tracing Metadata
            decision_context = {
                "state": sys_state.name,
                "priority": priority.name,
                "category": category.value,
                "policy": "allow" if allowed else "shed_token_bucket"
            }
            
            if not allowed and priority < PriorityLevel.ESSENTIAL:
                 return await self.respond_error(429, "Too Many Requests (Adaptive)", scope, receive, send, decision_context)

            # Global Lockdown
            if sys_state == SystemState.EMERGENCY and priority < PriorityLevel.ESSENTIAL:
                decision_context["policy"] = "shed_emergency"
                return await self.respond_error(503, "Emergency Lockdown", scope, receive, send, decision_context)
            
            # Maintenance Gate
            if await orchestrator.is_in_maintenance() and priority < PriorityLevel.HIGH:
                decision_context["policy"] = "shed_maintenance"
                return await self.respond_error(503, "System Maintenance", scope, receive, send, decision_context)

            # 3. SECURITY & PENALTY BOX
            # --------------------------
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            if await orchestrator.penalty_box.is_jailed(client_ip):
                decision_context["policy"] = "shed_security"
                return await self.respond_error(403, "Security Block", scope, receive, send, decision_context)

            # 4. LOAD SHEDDING & RESOURCE PROTECTION (Task 1.8)
            # -----------------------------------------
            if policy["shed"]:
                decision_context["policy"] = f"shed_policy_{sys_state.name}"
                return await self.respond_error(503, f"Load Shedding: {sys_state.name}", scope, receive, send, decision_context)

            # Connection Limits (Adaptive)
            effective_max = int(self.max_connections * policy["multiplier"])
            if self.active_connections >= effective_max and priority < PriorityLevel.ESSENTIAL:
                decision_context["policy"] = "shed_peak_capacity"
                return await self.respond_error(503, "Capacity Reached", scope, receive, send, decision_context)
                    
            # JIT Readiness Check (Intelligent Loading)
            try:
                target = "GRAPH" if category == RouteCategory.DATA_HEAVY else "DATABASE" if priority >= PriorityLevel.NORMAL else None
                if target:
                    await jit_manager.ensure_ready(target)
            except Exception as e:
                decision_context["policy"] = "shed_jit_init"
                return await self.respond_error(503, "Initializing", scope, receive, send, decision_context, retry_after=5)

            # 5. EXECUTION WITH DYNAMIC TIMEOUT & CONCURRENCY
            # -----------------------------------------------
            self.active_connections += 1
            timeout = self.base_timeout * policy["timeout_scale"]
            
            try:
                async with asyncio.timeout(timeout):
                    if category == RouteCategory.DATA_HEAVY:
                        # Priority Queueing for Heavy Routes (Adaptive)
                        wait_limit = 2.0 if sys_state >= SystemState.WARNING else 5.0
                        try:
                            async with asyncio.timeout(wait_limit):
                                async with self.heavy_semaphore:
                                    return await self.run_inner(scope, receive, send, headers, decision_context)
                        except (asyncio.TimeoutError, TimeoutError):
                            decision_context["policy"] = "shed_queue_timeout"
                            return await self.respond_error(503, "Queue Timeout", scope, receive, send, decision_context)
                    else:
                        return await self.run_inner(scope, receive, send, headers, decision_context)
            except (asyncio.TimeoutError, TimeoutError):
                decision_context["policy"] = "error_timeout"
                return await self.respond_error(504, "Timeout", scope, receive, send, decision_context)
            finally:
                self.active_connections = max(0, self.active_connections - 1)
        
        finally:
            orchestrator.report_request_end()

    async def run_inner(self, scope, receive, send, headers, decision_context):
        """Executes the actual application with adaptive compression and security headers."""
        
        # Adaptive Response Wrapping
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                
                # 1. CORS Enforcement
                origin = headers.get(b"origin", b"").decode()
                if origin:
                    allowed = origin if "*" in self.origins or origin in self.origins else self.origins[0]
                    msg_headers.append((b"Access-Control-Allow-Origin", allowed.encode()))
                    msg_headers.append((b"Access-Control-Allow-Credentials", b"true"))

                # 2. Security Headers
                msg_headers.append((b"X-Content-Type-Options", b"nosniff"))
                msg_headers.append((b"X-Frame-Options", b"DENY"))
                msg_headers.append((b"X-XSS-Protection", b"1; mode=block"))
                msg_headers.append((b"Strict-Transport-Security", b"max-age=31536000"))

                # 3. Task 1.10: Debug Tracing Header
                trace = f"S={decision_context['state']},P={decision_context['priority']},D={decision_context['policy']}"
                msg_headers.append((b"X-Middleware-Decision", trace.encode()))
                
                message["headers"] = msg_headers
            
            await send(message)
        
        return await self.app(scope, receive, send_wrapper)

    async def handle_options(self, scope, receive, send):
        """Handles CORS preflight requests efficiently."""
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()
        
        resp_headers = [
            (b"Access-Control-Allow-Methods", b"GET, POST, PUT, DELETE, OPTIONS, PATCH"),
            (b"Access-Control-Allow-Headers", b"*"),
            (b"Access-Control-Max-Age", b"86400"),
        ]
        
        if origin:
            allowed = origin if "*" in self.origins or origin in self.origins else self.origins[0]
            resp_headers.append((b"Access-Control-Allow-Origin", allowed.encode()))
            resp_headers.append((b"Access-Control-Allow-Credentials", b"true"))

        response = SafeJSONResponse(status_code=204, content=None, headers=dict((k.decode(), v.decode()) for k, v in resp_headers))
        return await response(scope, receive, send)

    async def respond_error(self, code: int, message: str, scope, receive, send, decision_context: Dict, retry_after: int = 15):
        """Standardized error responder for middleware-level rejections."""
        headers = {
            "X-Middleware-Decision": f"S={decision_context['state']},P={decision_context['priority']},D={decision_context['policy']}"
        }
        response = SafeJSONResponse(
            status_code=code,
            content={
                "error": True,
                "message": message,
                "code": code,
                "retry_after": retry_after,
                "trace": decision_context["policy"]
            },
            headers=headers
        )
        return await response(scope, receive, send)
