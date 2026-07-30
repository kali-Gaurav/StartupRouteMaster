import asyncio
import logging
from starlette.types import ASGIApp, Scope, Receive, Send

logger = logging.getLogger("nexus.lazy_boot")

# Global flag to ensure we only boot once
_boot_initiated = False
_boot_lock = asyncio.Lock()

class LazyBootMiddleware:
    """
    [Instant Startup] Triggers heavy background preprocessing ONLY after the first request.
    This allows the application to start in milliseconds and pass initial health checks.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        global _boot_initiated
        
        if scope["type"] == "http" and not _boot_initiated:
            async with _boot_lock:
                if not _boot_initiated:
                    _boot_initiated = True
                    logger.info("🚀 [LAZY_BOOT] First request detected. Triggering background preprocessing...")
                    
                    # Import here to avoid heavy loads at module level
                    from core.infrastructure.lifespan import _nexus_background_boot
                    from fastapi import FastAPI
                    
                    # We need the app instance. In a middleware, we don't easily have it
                    # unless we pass it or it's stored in scope.
                    # FastAPI stores the app in scope['app']
                    app_instance = scope.get("app")
                    if app_instance:
                        asyncio.create_task(_nexus_background_boot(app_instance))
                    else:
                        logger.warning("⚠️ [LAZY_BOOT] Could not find app instance in scope.")

        await self.app(scope, receive, send)
