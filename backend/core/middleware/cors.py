def get_cors_config():
    """Returns production-grade CORS settings for RouteMaster V3."""
    import os
    from database.config import Config

    origins = [
        # Local dev
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        # Production Vercel domains
        "https://routemaster.vercel.app",
        "https://routemaster-transit.vercel.app",
        # Allow any Vercel preview deployment for this project
        "https://routemaster-frontend.vercel.app",
    ]

    # Allow custom domain from env (set FRONTEND_URL on Render)
    custom_frontend = os.getenv("FRONTEND_URL", "").strip()
    if custom_frontend and custom_frontend not in origins:
        origins.append(custom_frontend)

    # In non-production, be slightly more permissive
    if Config.ENVIRONMENT != "production":
        origins.append("http://localhost:8000")
        origins.append("http://127.0.0.1:8000")

    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Process-Time", "X-Nexus-State", "X-Nexus-ID", "X-Nexus-Duration-MS"]
    }

