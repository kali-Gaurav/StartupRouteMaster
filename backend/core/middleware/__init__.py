from .cors import get_cors_config

__all__ = [
    "setup_middleware"
]

def setup_middleware(app):
    """
    [Task 3.10] Nexus Atomic Middleware Gate.
    Consolidates 5+ legacy middlewares into a single high-speed Nexus I/O Gate.
    Replaces: Observability, DB Lifecycle, Rate-Limit, and Smart Engine layers.
    """
    from core.nexus.middleware import NexusIOGate
    # 1. Master I/O Gate
    app.add_middleware(NexusIOGate)
    
    # 2. CORS (Specialized security layer)
    from fastapi.middleware.cors import CORSMiddleware
    from .cors import get_cors_config
    app.add_middleware(CORSMiddleware, **get_cors_config())
    
    return app
