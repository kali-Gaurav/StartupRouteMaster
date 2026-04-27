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
    from .guardian import ScraperGuardianMiddleware
    from .localization import GeoAdaptiveLocalizationMiddleware
    from core.waf import SovereignWAFMiddleware
    
    # 0. Sovereign WAF (Outer Perimeter)
    app.add_middleware(SovereignWAFMiddleware)
    
    # 1. Master I/O Gate
    app.add_middleware(NexusIOGate)
    
    # 2. Guardian Shield & Geo-Adaptive Localization
    app.add_middleware(ScraperGuardianMiddleware)
    app.add_middleware(GeoAdaptiveLocalizationMiddleware)
    
    # 3. CORS (Specialized security layer)
    from fastapi.middleware.cors import CORSMiddleware
    from .cors import get_cors_config
    app.add_middleware(CORSMiddleware, **get_cors_config())
    
    return app
