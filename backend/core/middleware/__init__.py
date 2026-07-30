from core.nexus.middleware import NexusIOGate
from .cors import get_cors_config

__all__ = [
    "setup_middleware"
]

from core.nexus.middleware import NexusIOGate
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
    from .lazy_boot import LazyBootMiddleware
    # 00. Lazy Boot - Innermost (closest to app logic)
    app.add_middleware(LazyBootMiddleware)

    from .guardian import ScraperGuardianMiddleware
    from .localization import GeoAdaptiveLocalizationMiddleware
    from core.resilience.waf import SovereignWAFMiddleware
    from core.nexus.middleware import NexusIOGate
    
    # 1. Nexus Master I/O Gate
    app.add_middleware(NexusIOGate)
    
    # 2. Sovereign WAF
    app.add_middleware(SovereignWAFMiddleware)
    
    # 3. Guardian Shield & Geo-Adaptive Localization
    app.add_middleware(ScraperGuardianMiddleware)
    app.add_middleware(GeoAdaptiveLocalizationMiddleware)
    
    # [Task 1.3] CORS (Specialized security layer) 
    # Must be absolute outermost (last added) to catch all responses including rejects.
    from fastapi.middleware.cors import CORSMiddleware
    from .cors import get_cors_config
    app.add_middleware(CORSMiddleware, **get_cors_config())
    
    return app
