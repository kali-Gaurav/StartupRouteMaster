# # backend/core/middleware/__init__.py
# \"\"\"
# Central Registry for RouteMaster V3 Middleware Stack.
# Exports all specialized middlewares and provides a unified setup tool.
# \"\"\"

from .observability import ObservabilityMiddleware
from .db_lifecycle import DatabaseLifecycleMiddleware
from .rate_limit import RateLimitMiddleware
from .traffic_profiler import AsyncTrafficAnalyzer
from .unified_engine import UnifiedSmartMiddlewareEngine
from .control import traffic_control

__all__ = [
    "ObservabilityMiddleware",
    "DatabaseLifecycleMiddleware",
    "RateLimitMiddleware",
    "AsyncTrafficAnalyzer",
    "UnifiedSmartMiddlewareEngine",
    "traffic_control",
    "setup_middleware"
]

def setup_middleware(app):
    # \"\"\"
    # Installs the core middleware stack in the recommended production order.
    # Execution order (bottom-up in Starlette/FastAPI):
    # 1. Observability (Outer-most - captures everything)
    # 2. Database Lifecycle (Ensures DB session per request)
    # 3. Traffic Profiler (Telemetry and ML-offloading)
    # 4. Rate Limiting (Distributed Protection)
    # 5. Unified Smart Engine (The \"Brain\": Throttling, Load Shedding, Proxying)
    # \"\"\"
    
    # Bottom of the list = First to receive request, Last to finish response
    # 1. Observability (Tracing, Logging, SLA)
    app.add_middleware(ObservabilityMiddleware)
    
    # 2. DB Lifecycle (Session management)
    app.add_middleware(DatabaseLifecycleMiddleware)
    
    # 3. Traffic profiling (Async telemetry)
    app.add_middleware(AsyncTrafficAnalyzer)
    
    # 4. Global Rate Limiting (Redis-based)
    app.add_middleware(RateLimitMiddleware)
    
    # 5. Core Resilience & Intelligence (The Smart Engine)
    # This should be inner-most or near-inner to respect protections above it
    app.add_middleware(UnifiedSmartMiddlewareEngine)
    
    return app
