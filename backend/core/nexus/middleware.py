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

        # Adaptive Load Shedding (Relaxed for Local Dev)
        mem = psutil.virtual_memory()
        if mem.percent > 99:
             logger.critical(f"[NEXUS:GATE] CRITICAL LOAD SHEDDING (RAM: {mem.percent}%).")
             response = Response(content="SYSTEM_OVERLOADED", status_code=503)
             await response(scope, receive, send)
             return

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
            # Log standard completions (simplified)
            if logger.isEnabledFor(logging.DEBUG):
                 logger.debug(f"[NEXUS:{request_id}] Finished in {duration}ms")

nexus_io_gate = NexusIOGate
