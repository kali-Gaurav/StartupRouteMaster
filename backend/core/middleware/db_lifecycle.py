import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from database.multiplexer import get_multiplexed_db

logger = logging.getLogger("db-lifecycle")

class DatabaseLifecycleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Only inject for API routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        # Generate multiplexer session
        db_gen = get_multiplexed_db()
        db = await db_gen.__anext__()
        
        # Inject into request state
        request.state.db = db
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"🔗 DB Lifecycle: Request failed, rolling back session. Error: {e}")
            await db.rollback()
            raise e
        finally:
            try:
                await db_gen.__anext__()
            except StopAsyncIteration:
                pass
