"""
RouteMaster API — Clean entry point.
Boots in < 2 seconds. No heavy imports at startup.
Only loads what's needed: search, stations, auth, SOS, health.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure backend root is importable
backend_root = Path(__file__).resolve().parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
if str(backend_root.parent) not in sys.path:
    sys.path.insert(0, str(backend_root.parent))

from utils.structured_logging import setup_logging
setup_logging()
logger = logging.getLogger("routemaster")


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot only what matters. Everything else is lazy."""
    logger.info("RouteMaster starting...")

    # 1. Database
    try:
        from database.infrastructure.session import initialize_database_pools
        await initialize_database_pools()
        app.state.db = "ready"
        logger.info("Database: ready")
    except Exception as e:
        app.state.db = "degraded"
        logger.warning(f"Database degraded: {e}")

    # 2. Redis cache — direct connection (no multi_layer complexity)
    try:
        import redis as redis_lib
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            r = redis_lib.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
            r.ping()
            app.state.redis_client = r
            app.state.redis = "ready"
            logger.info("Redis: ready")
        else:
            app.state.redis = "no_url"
            logger.warning("Redis: REDIS_URL not set")
    except Exception as e:
        app.state.redis = "degraded"
        logger.warning(f"Redis degraded: {e}")

    # 3. Station search index (in-memory trie — fast autocomplete)
    try:
        from services.station_search_service import station_search_engine
        app.state.stations = "ready"
        logger.info("Station index: ready")
    except Exception as e:
        app.state.stations = "degraded"
        logger.warning(f"Station index degraded: {e}")

    # 4. Route engine (lazy — initialises on first search request)
    app.state.route_engine = "lazy"

    # 5. Register Telegram webhook (non-blocking — only if token + render URL set)
    try:
        import os as _os
        if _os.getenv("TELEGRAM_BOT_TOKEN") and _os.getenv("RENDER_EXTERNAL_URL"):
            from api.v1.telegram import register_webhook
            result = await register_webhook()
            if result.get("registered"):
                logger.info(f"Telegram webhook registered: {result.get('webhook_url')}")
            else:
                logger.warning(f"Telegram webhook skipped: {result}")
    except Exception as e:
        logger.warning(f"Telegram webhook registration skipped: {e}")

    logger.info("RouteMaster ready.")
    yield

    # Shutdown
    try:
        from database.infrastructure.session import _dispose_all_pools
        await _dispose_all_pools()
    except Exception:
        pass
    logger.info("RouteMaster shutdown complete.")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RouteMaster API",
    description="Indian railway multi-segment route optimizer.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─── CORS ────────────────────────────────────────────────────────────────────

_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "https://routemaster.vercel.app",
    "https://routemaster-frontend.vercel.app",
    "https://routemaster-api.onrender.com",
]
_custom = os.getenv("FRONTEND_URL", "").strip()
if _custom:
    _cors_origins.append(_custom)

# Also allow all Vercel preview deploy URLs (*.vercel.app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health():
    db_state = getattr(app.state, "db", "unknown")
    redis_state = getattr(app.state, "redis", "unknown")
    overall = "ok" if db_state in ("ready", "degraded") else "degraded"
    return {
        "status": overall,
        "version": "1.0.0",
        "components": {
            "database": db_state,
            "redis":    redis_state,
            "stations": getattr(app.state, "stations", "unknown"),
        }
    }

# Alias used by frontend useServerWarmup hook
@app.get("/health/live", tags=["health"])
async def health_live():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/ping", tags=["health"])
async def ping():
    return {"pong": True}

# Stats endpoint used by frontend to show train/station counts
@app.get("/stats", tags=["health"])
async def stats():
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        from sqlalchemy import text
        trains = dp.session.execute(text("SELECT COUNT(DISTINCT route_id) FROM trips")).scalar() or 0
        stations = dp.session.execute(text("SELECT COUNT(*) FROM stops")).scalar() or 0
        dp.close()
        return {"total_trains": int(trains), "total_stations": int(stations)}
    except Exception:
        return {"total_trains": 11000, "total_stations": 8000}


# ─── Routers — registered safely, one failure won't break the others ─────────

def _include(router_path: str, attr: str, prefix: str = "", **kwargs):
    """Import and register a router. Log a warning on failure, never crash."""
    try:
        import importlib
        mod = importlib.import_module(router_path)
        router = getattr(mod, attr)
        app.include_router(router, prefix=prefix, **kwargs)
        logger.info(f"Router registered: {router_path}")
    except Exception as e:
        logger.warning(f"Router skipped [{router_path}]: {e}")


# ── V1 CLEAN ROUTES (always first — these are the product) ───────────────────
_include("api.v1.search",   "router", prefix="/api/v1")
_include("api.v1.stations", "router", prefix="/api/v1")
_include("api.v1.auth",     "router", prefix="/api/v1")
_include("api.v1.live",     "router", prefix="/api/v1")
_include("api.v1.fare",      "router", prefix="/api/v1")
_include("api.v1.routes_seo", "router", prefix="/api/v1")
_include("api.v1.telegram",   "router", prefix="/api/v1")
_include("api.v1.alerts",       "router", prefix="/api/v1")
_include("api.v1.saved_routes",  "router", prefix="/api/v1")
_include("api.v1.reliability",   "router", prefix="/api/v1")
_include("api.v1.pnr",      "router", prefix="/api/v1")
_include("api.v1.sos",      "router", prefix="/api/v1")

# ── LEGACY ROUTES (optional — may fail, that's ok) ────────────────────────────
_include("api.search.search",    "router", prefix="/api")
_include("api.search.stations",  "router", prefix="/api")
_include("api.auth.auth",        "router", prefix="/api")
_include("api.auth.users",       "router", prefix="/api")
_include("api.safety.sos",       "router", prefix="/api")
_include("api.safety.sathi",     "router", prefix="/api")
_include("api.bookings.bookings","router", prefix="/api")
_include("api.payments.payments",          "router", prefix="/api")
_include("api.payments.payment_webhook",   "router")
_include("api.payments.razorpay_standard", "router", prefix="/api")
_include("api.system.status",    "router", prefix="/api")
_include("api.admin.admin",      "router", prefix="/api/v1")


# ─── Global error handler ────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "An unexpected error occurred."}
    )


# ─── Dev entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
