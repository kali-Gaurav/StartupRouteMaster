def get_cors_config():
    """Returns production-grade CORS settings for RouteMaster V3."""
    return {
        "allow_origins": ["*"], # Update for production whitelist
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Process-Time", "X-Nexus-State", "X-Nexus-ID", "X-Nexus-Duration-MS"]
    }
