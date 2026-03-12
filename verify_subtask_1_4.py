import asyncio
import logging
from starlette.types import Scope

# Mock objects for ASGI
async def mock_receive(): return {"type": "lifespan.startup"}
async def mock_send(message): pass

async def verify_scope_check(middleware_class, name):
    logger = logging.getLogger("verify")
    logger.info(f"Verifying {name}...")
    
    # Mock app that just returns
    async def mock_app(scope, receive, send):
        scope["passed_through"] = True
        return

    mw = middleware_class(mock_app)
    
    # 1. Test with non-HTTP scope
    scope = {"type": "lifespan", "passed_through": False}
    await mw(scope, mock_receive, mock_send)
    assert scope["passed_through"] is True, f"{name} did not pass through non-HTTP scope"
    logger.info(f"✅ {name} handles non-HTTP scope correctly.")

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Import actual middlewares
    from backend.app import UnifiedJITMiddleware
    from backend.core.middleware.observability import ObservabilityMiddleware
    from backend.core.middleware.db_lifecycle import DatabaseLifecycleMiddleware
    from backend.core.middleware.rate_limit import RateLimitMiddleware
    from backend.core.middleware.traffic_profiler import AsyncTrafficAnalyzer
    
    await verify_scope_check(UnifiedJITMiddleware, "UnifiedJITMiddleware")
    await verify_scope_check(ObservabilityMiddleware, "ObservabilityMiddleware")
    await verify_scope_check(DatabaseLifecycleMiddleware, "DatabaseLifecycleMiddleware")
    await verify_scope_check(RateLimitMiddleware, "RateLimitMiddleware")
    await verify_scope_check(AsyncTrafficAnalyzer, "AsyncTrafficAnalyzer")

if __name__ == "__main__":
    asyncio.run(main())
