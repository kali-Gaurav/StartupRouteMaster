import logging
from starlette.types import ASGIApp, Scope, Receive, Send
from database.multiplexer import get_multiplexed_db

logger = logging.getLogger("db-lifecycle")

class DatabaseLifecycleMiddleware:
    """
    Native ASGI Database Lifecycle Middleware.
    Provides robust DB session management (CQRS Multiplexer) with guaranteed 
    rollback on errors and clean closure.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        # Only manage DB for /api routes to save resources on static/root/health
        if not path.startswith("/api"):
            return await self.app(scope, receive, send)

        # 1. Initialize Generator
        db_gen = get_multiplexed_db()
        try:
            db = await db_gen.__anext__()
        except Exception as e:
            logger.error(f"❌ DB Lifecycle: Failed to initialize session: {e}")
            # Fallback: let app handle or return error
            return await self.app(scope, receive, send)
        
        # 2. Inject into scope (FastAPI request.state reads from scope['state'])
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["db"] = db
        
        # 3. Request Execution
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            # 4. Global Rollback on unhandled exception
            logger.error(f"🔗 DB Lifecycle: Request failed, rolling back session. RID: {scope.get('request_id', 'N/A')}")
            try:
                await db.rollback()
            except Exception as rb_err:
                logger.error(f"❌ DB Lifecycle: Rollback failed: {rb_err}")
            
            # Standardized internal crash response
            from backend.utils.responses import SafeJSONResponse
            response = SafeJSONResponse(
                status_code=500,
                content={"error": True, "message": "Internal Database Lifecycle Error", "detail": str(e)}
            )
            if not scope.get("_response_started", False):
                return await response(scope, receive, send)
            else:
                raise e # Already started sending, must raise
        finally:
            # 5. Guaranteed Closure via Generator Exhaustion
            try:
                await db_gen.__anext__()
            except StopAsyncIteration:
                pass
            except Exception as close_err:
                logger.error(f"❌ DB Lifecycle: Error during session closure: {close_err}")
