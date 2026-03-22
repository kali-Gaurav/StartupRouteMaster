import logging
import secrets
from fastapi import FastAPI, Request, HTTPException
from core.orchestrator import orchestrator
from utils.responses import SafeJSONResponse

logger = logging.getLogger("routemaster.exceptions")

def setup_exception_handlers(app: FastAPI):
    """
    Task 2: Modularized Exception Handlers.
    Registers global handlers for catastrophic and HTTP errors.
    """
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_id = secrets.token_hex(4).upper()
        logger.error(f"🚨 SYSTEM PANIC [{error_id}]: {type(exc).__name__}: {exc}", exc_info=True)
        
        client_ip = request.client.host if request.client else "unknown"
        await orchestrator.penalty_box.report_error(client_ip)
        
        return SafeJSONResponse(
            status_code=500,
            content={
                "error": True, 
                "message": "RouteMaster Protocol: Safe Mode Active.", 
                "protocol_code": f"ERR_SYSTEM_PANIC_{error_id}",
                "type": type(exc).__name__
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return SafeJSONResponse(
            status_code=exc.status_code,
            content={"error": True, "message": exc.detail}
        )
