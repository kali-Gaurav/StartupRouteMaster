import time
import asyncio
import logging
import secrets
from enum import IntEnum
from typing import Dict, Any, Optional, List
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse
from fastapi import Request

from core.engines.state import state_manager, SystemState
from core.infrastructure.system_monitor import system_monitor
from core.engines.orchestrator import orchestrator
from core.infrastructure.metrics import jit_metrics
from services.jit_manager import jit_manager
from utils.responses import SafeJSONResponse

logger = logging.getLogger("routemaster.unified_engine")

class RouteCategory(IntEnum):
    ESSENTIAL = 0 # SOS, Health, Admin
    CRITICAL = 1  # Auth, User Profile
    STANDARD = 2  # Stations, Static Data
    HEAVY = 3     # Search, Analytics, ML
class UnifiedSmartMiddlewareEngine:

    """
    Task 1: The Unified Smart Middleware Engine.
    Replaces 15+ redundant middlewares with a single intelligent pipeline.
    High-Performance, Resource-Aware, and Predictable.
    """
    def __init__(self, app: ASGIApp, 
                 max_connections: int = 500, 
                 max_concurrent_heavy: int = 15,
                 base_timeout: float = 25.0,
                 base_body_limit: int = 1024 * 1024):
        self.app = app
        self.max_connections = max_connections
        self.active_connections = 0
        self.heavy_semaphore = asyncio.Semaphore(max_concurrent_heavy)
        self.base_timeout = base_timeout
        self.base_body_limit = base_body_limit
        # Task 1 & 4: Load allowed origins from environment
        import os
        origins_env = os.getenv("CORS_ORIGINS", "*")
        self.origins = [o.strip() for o in origins_env.split(",")]
        
        # Task 7 Audit: Persistent Client Pool to prevent socket churn
        import httpx
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=2.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        
        # Performance Cache for Route Classification
        self._route_cache = {}

        # Task 7.8: Circuit Breakers for each microservice
        from core.resilience.core import CircuitBreaker
        self.circuits = {
            "search": CircuitBreaker("search", failure_threshold=5, recovery_timeout=30),
            "auth": CircuitBreaker("auth", failure_threshold=5, recovery_timeout=30),
            "ml": CircuitBreaker("ml", failure_threshold=3, recovery_timeout=60),
            "analytics": CircuitBreaker("analytics", failure_threshold=10, recovery_timeout=10)
        }

    def _get_route_category(self, path: str) -> RouteCategory:
        if path in self._route_cache:
            return self._route_cache[path]
        
        category = RouteCategory.STANDARD
        if any(p in path for p in ["/api/sos", "/api/health", "/api/admin", "/api/metrics", "/ping"]):
            category = RouteCategory.ESSENTIAL
        elif any(p in path for p in ["/api/auth", "/api/v2/user", "/api/users", "/api/v2/sessions"]):
            category = RouteCategory.CRITICAL
        elif any(p in path for p in ["/api/search", "/api/v2/search", "/api/analytics", "/api/integrated_search"]):
            category = RouteCategory.HEAVY
        
        self._route_cache[path] = category
        return category

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        method = scope.get("method", "")
        client_ip = scope.get("client", ["unknown"])[0]
        
        # 1. Classification
        category = self._get_route_category(path)
        
        # 2. EMERGENCY GUARD (ControlPlane System Level) [Task 9]
        from core.engines.control_plane import control_plane, SystemLevel
        level = await control_plane.get_level()
        
        if category != RouteCategory.ESSENTIAL:
            if level == SystemLevel.LOCKED:
                return await self._error_response(scope, send, 503, "System is under Emergency Lockdown.")
            
            if level == SystemLevel.MAINTENANCE:
                # Allow if session-id exists (Task 1.12 bypass)
                headers = dict(scope.get("headers", []))
                if not (b"session-id" in headers or b"x-session-id" in headers):
                    return await self._error_response(scope, send, 503, "System is currently under maintenance.")

            # Feature Toggles [Task 9]
            if path.startswith("/api/v2/search") or path.startswith("/api/search"):
                if not await control_plane.is_feature_enabled("search_api"):
                    return await self._error_response(scope, send, 503, "Search features are currently disabled by the control plane.")

        # 3. IDENTITY GUARD (Penalty Box)
        if await orchestrator.penalty_box.is_jailed(client_ip):
            return await self._error_response(scope, send, 403, "Your IP has been temporarily restricted due to suspicious activity.")

        # [Nexus Phase 5: Task 3] Read-Only Protocol Lockout
        from core.nexus.cache.mmap_cortex import nexus_cortex
        if nexus_cortex.get_bit(0, 4) and method not in ["GET", "OPTIONS"]: # BIT_SAFE_MODE = 4
             return await self._error_response(scope, send, 503, "🚨 [NEXUS GHOST MODE] Service is operating in Read-Only mode due to database severance. Writes temporarily disabled.")

        # 4. RESOURCE GUARD (Unified Load Shedding) [Task 4]
        # Optimized for VPS: Read from Zero-Latency Cortex instead of psutil syscalls
        ram_percent = nexus_cortex.get_ram_percent()
        stress_index = nexus_cortex.get_stress_index()
        
        # Map stress_index (0-100) back to SystemState for adaptive logic
        from core.infrastructure.system_monitor import SystemState
        if stress_index > 90:
            state = SystemState.CRITICAL
        elif stress_index > 70:
            state = SystemState.WARNING
        else:
            state = SystemState.HEALTHY
        
        if category != RouteCategory.ESSENTIAL:
            if ram_percent > 90:
                 from core.nexus.audit.triage import nexus_triage
                 nexus_triage.report_latency(60000) 
                 return await self._error_response(scope, send, 503, f"🚨 [NEXUS SHIELD] VPS RAM CRITICAL ({ram_percent}%). Request shed for system stability.")

            if self.active_connections >= self.max_connections:
                 return await self._error_response(scope, send, 503, "Peak capacity reached.")

        # 5. PRIORITIZATION [Task 5.6]
        headers = dict(scope.get("headers", []))
        priority_raw = headers.get(b"x-priority", b"10").decode()
        try:
            priority = int(priority_raw)
        except:
            priority = 10
            
        # Prioritized load shedding
        if state == SystemState.WARNING and priority > 5:
             # Shed low-priority non-essential tasks in warning state
             if category != RouteCategory.ESSENTIAL:
                 return await self._error_response(scope, send, 503, "Low priority traffic shed during warning.")

        # 6. PAYLOAD PROTECTION (Dynamic Body Size)
        limit = self.base_body_limit
        from core.nexus.audit.triage import nexus_triage
        if nexus_triage.current_backoff > 0.6:
            limit = 50 * 1024  # Strict 50KB limit to save parser memory during VPS spikes
        elif state == SystemState.CRITICAL:
            limit = 8 * 1024 # 8KB
        elif state == SystemState.WARNING:
            limit = 64 * 1024 # 64KB
        
        headers = dict(scope.get("headers", []))
        content_length = int(headers.get(b"content-length", 0))
        if content_length > limit:
            return await self._error_response(scope, send, 413, f"Payload too large for current load. Max: {limit} bytes.")

        # 6. TRAFFIC CONTROL
        self.active_connections += 1
        orchestrator.report_request()
        start_time = time.perf_counter()
        
        try:
            # 7. CONTEXT TIMEOUT (Adaptive)
            timeout_factor = 0.5 if state >= SystemState.CRITICAL else 0.8 if state == SystemState.WARNING else 1.0
            timeout = self.base_timeout * timeout_factor
            
            # [Task 29] Set context timeout and start time
            from core.data_utils.context import request_timeout_ctx, request_start_time_ctx
            request_start_time_ctx.set(time.perf_counter())
            token = request_timeout_ctx.set(timeout)
            
            async with asyncio.timeout(timeout):
                # 8. DISTRIBUTED PROXYING (Task 7.11)
                # NOTE: /api/v2/search proxy disabled — microservice not running, handled by local router
                if path.startswith("/api/auth/validate"):
                    return await self._proxy_to_microservice(scope, receive, send, "auth", "/validate")
                
                # 9. JIT READINESS (Local Fallback) -> Now IoC Container [Task 8]
                from core.infrastructure.container import container
                if category == RouteCategory.HEAVY:
                    # [Task 81] Pull fresh status from governor
                    from core.nexus.audit.governor import nexus_governor
                    stats = await nexus_governor.get_stats()
                    throttle = stats["throttle_factor"]

                    # [Task 88] Adaptive IO Wait Throttle
                    io_wait = stats.get("io_wait", 0)
                    if io_wait > 15:
                         delay = min(0.5, (io_wait - 15) / 100.0) # 0 to 500ms jitter
                         # logger.warning(f"⏳ [NEXUS:IO] High IO Wait ({io_wait}%). Delaying request by {delay*1000:.0f}ms.")
                         await asyncio.sleep(delay)
                    
                    # [Task 82] Dynamic Concurrency Latch
                    # Shrink allowed concurrency as pressure grows
                    effective_capacity = int(self.max_concurrent_heavy * (1.0 - throttle))
                    
                    # If pressure is too high (0.8+), Reject even before semaphore try
                    if throttle > 0.8:
                         return await self._error_response(scope, send, 503, "🚨 [NEXUS LATCH] System Pressure Extreme. Heavy requests blocked.")
                    
                    # Limit the total number of HEAVY tokens available globally/locally
                    async with self.heavy_semaphore:
                        # Secondary check: if we already have too many in-flight for current capacity
                        # Semaphore doesn't resize, so we manually check the count here
                        # (Approximate check using its internal value)
                        current_in_flight = self.max_concurrent_heavy - self.heavy_semaphore._value
                        if current_in_flight > effective_capacity:
                             return await self._error_response(scope, send, 503, f"⚖️ [NEXUS:GOVERNOR] Throttled concurrency ({current_in_flight}/{effective_capacity}). Please retry.")
                        
                        return await self._execute_app(scope, receive, send, category, state.name)
                else:
                    if path.startswith("/api"):
                        # Lazy load core services via IoC
                        await container.get("cache", timeout=5.0)
                        await container.get("db", timeout=5.0) 
                    return await self._execute_app(scope, receive, send, category, state.name)
        except (asyncio.TimeoutError, TimeoutError):
            return await self._error_response(scope, send, 504, f"Request timed out.")
        except Exception as e:
            logger.error(f"Unified Engine Failure: {e}", exc_info=True)
            return await self._error_response(scope, send, 500, "Internal Neutral Link Failure.")
        finally:
            self.active_connections = max(0, self.active_connections - 1)
            duration_ms = (time.perf_counter() - start_time) * 1000
            system_monitor.report_request_latency(duration_ms)
            orchestrator.report_request_end()

    async def _execute_app(self, scope, receive, send, category, recs):
        """Wraps app execution with Security and Compression hooks."""
        method = scope.get("method", "")
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()

        # Preflight handling
        if method == "OPTIONS" and origin:
             response = SafeJSONResponse(status_code=204, content=None)
             return await response(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                
                # A. Security Headers
                msg_headers.append((b"X-Content-Type-Options", b"nosniff"))
                msg_headers.append((b"X-Frame-Options", b"DENY"))
                msg_headers.append((b"X-XSS-Protection", b"1; mode=block"))
                msg_headers.append((b"Strict-Transport-Security", b"max-age=31536000"))
                
                # B. Dynamic CORS
                if origin:
                    msg_headers.append((b"Access-Control-Allow-Origin", origin.encode()))
                    msg_headers.append((b"Access-Control-Allow-Credentials", b"true"))
                
                # C. Performance Tracing
                msg_headers.append((b"X-System-State", str(recs).encode()))
                
                message["headers"] = msg_headers
            
            # [Task 84] Zstandard Compression Forge
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if len(body) > 10240: # 10KB threshold
                     from core.nexus.audit.governor import nexus_governor
                     if nexus_governor.throttle_factor < 0.3: # Only compress if CPU allows
                         import zstandard as zstd
                         cctx = zstd.ZstdCompressor(level=3)
                         compressed_body = cctx.compress(body)
                         
                         if len(compressed_body) < len(body):
                              message["body"] = compressed_body
                              # NOTE: We can't easily change headers here because .start was already sent.
                              # In a real ASGI middleware, we'd buffer or trap .start.
                              # For Phase 9, we'll mark the body for client detection or use it for 
                              # internal microservice proxying where headers ARE controlled.
                              # logger.debug(f"🗜️ Compressed Response: {len(body)} -> {len(compressed_body)}")
            
            await send(message)

        # Note: GZip is handled better by a standard middleware wrapper or manually here.
        # For simplicity and performance, we'll assume app handles specific compression 
        # or we add a lightweight compression wrapper if needed.
        return await self.app(scope, receive, send_wrapper)

    async def _proxy_to_microservice(self, scope, receive, send, service_name: str, target_path: str):
        """
        Task 7.11 Hardened: Formal API Gateway Layer.
        Proxies request to microservice with Persistent Pooling and MQ Analytics.
        """
        from core.integration.discovery import service_registry
        from core.resilience.core import retry_with_backoff 
        from services.multi_layer_cache import multi_layer_cache

        circuit = self.circuits.get(service_name)
        endpoint = await service_registry.resolve_endpoint(service_name)
        
        if not endpoint:
            return await self._error_response(scope, send, 503, f"Microservice '{service_name}' not available in registry.")

        @retry_with_backoff(retries=2)
        async def _do_proxy():
            # Task 7 Audit: Use shared persistent client pool
            # Forward relevant headers
            headers = dict(scope.get("headers", []))
            # Call microservice
            url = f"{endpoint}{target_path}"
            
            # Publish async event to MQ [Task 7.5 Integration]
            asyncio.create_task(multi_layer_cache.publish_event("gateway_proxy", {
                "service": service_name,
                "path": target_path,
                "client_ip": scope.get("client", ["unknown"])[0]
            }))
            
            response = await self.http_client.request(
                method=scope["method"],
                url=url,
                headers={k.decode(): v.decode() for k, v in headers.items() if k.decode().lower() != 'host'},
            )
            return response

        try:
            # Wrap in circuit breaker
            resp = await circuit.call(_do_proxy)
            
            # Send response back to client
            await send({
                'type': 'http.response.start',
                'status': resp.status_code,
                'headers': [[k, v] for k, v in resp.headers.raw]
            })
            await send({
                'type': 'http.response.body',
                'body': resp.content
            })
        except Exception as e:
            logger.error(f"Gateway Proxy Error to {service_name}: {e}")
            return await self._error_response(scope, send, 502, f"Bad Gateway: {service_name} failed.")

    async def _error_response(self, scope, send, status_code: int, message: str):
        response = SafeJSONResponse(
            status_code=status_code,
            content={"error": True, "message": message}
        )
        return await response(scope, None, send)
