import logging
import time
import uuid
import psutil
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import Response
from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState

logger = logging.getLogger("nexus.io_gate")

class NexusIOGate:
    """
    [Task 3.1 & 3.2] Master High-Speed ASGI Middleware Gate.
    Raw ASGI implementation to support high-intensity streaming (SSE/WebSockets).
    Consolidates: Observability, Load-Shedding, and Security.
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # [Task 3.4] X-Nexus-Trace Protocol
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        
        # 1. IP Check
        client_ip = scope.get("client", ["unknown"])[0]
        from core.nexus.security.f2b_watcher import f2b_watcher
        if client_ip in f2b_watcher.blacklist:
             logger.warning(f"[NEXUS:GATE] BLOCKING BLACKLISTED IP: {client_ip}")
             response = Response(content="SERVICE_TERMINATED_IP_BANNED", status_code=403)
             await response(scope, receive, send)
             return

        # [Task 121: Elite Load-Shedding] Proactive Protection for 1-2GB VPS
        import os
        max_ram = float(os.getenv("NEXUS_MAX_RAM", "95.0"))
        max_cpu = float(os.getenv("NEXUS_MAX_CPU", "90.0"))
        force_continue = os.getenv("NEXUS_FORCE_CONTINUE_ON_STRESS", "true").lower() == "true"
        
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None) # Fast, non-blocking check
        
        # We shed load UNLESS it's a critical path (SOS/Health) or forced continue
        path = scope['path']
        is_critical = "sos" in path or "health" in path or "ping" in path
        
        if not is_critical and not force_continue:
            if mem.percent > max_ram:
                 logger.critical(f"[NEXUS:GATE] SHEDDING (RAM: {mem.percent}%). Path: {path}")
                 response = Response(content="SYSTEM_OVERLOADED_RAM", status_code=503)
                 await response(scope, receive, send)
                 return

            if cpu > max_cpu:
                 logger.critical(f"[NEXUS:GATE] SHEDDING (CPU: {cpu}%). Path: {path}")
                 response = Response(content="SYSTEM_OVERLOADED_CPU", status_code=503)
                 await response(scope, receive, send)
                 return
        elif not is_critical and force_continue:
            if mem.percent > max_ram or cpu > max_cpu:
                 # ALERT ADMIN instead of denial
                 logger.critical(f"⚠️ [NEXUS:ADMIN_ALERT] Resource Pressure High! (CPU: {cpu}%, RAM: {mem.percent}%). Path: {path}")

        logger.debug(f"[NEXUS:{request_id}] {scope['method']} {scope['path']} from {client_ip}")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                
                # Trace & Branding
                msg_headers.append((b"X-Nexus-ID", request_id.encode()))
                msg_headers.append((b"X-Nexus-State", nexus_boot.state.value.encode()))
                
                duration = round((time.perf_counter() - start_time) * 1000, 2)
                msg_headers.append((b"X-Nexus-Duration-MS", str(duration).encode()))
                
                message["headers"] = msg_headers
            
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            logger.error(f"[NEXUS:{request_id}] Unhandled Engine Error: {e}")
            from core.exceptions import handle_engine_crash
            # Note: handle_engine_crash must return a starlette Response
            response = await handle_engine_crash(e)
            await response(scope, receive, send)
        finally:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Record telemetry
            await nexus_boot.telemetry.record_request(duration)

            # Log standard completions (simplified)
            if logger.isEnabledFor(logging.DEBUG):
                 logger.debug(f"[NEXUS:{request_id}] Finished in {duration}ms")

nexus_io_gate = NexusIOGate
