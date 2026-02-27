from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
from datetime import datetime
import os
import asyncio
from contextlib import asynccontextmanager

from slowapi.errors import RateLimitExceeded

from worker import start_reconciliation_worker, stop_reconciliation_worker
from database.config import Config
from database import init_db, close_db
from api import search, routes, payments, admin, chat, users, reviews, auth, status, sos, flow, websockets, bookings, realtime
from utils.limiter import limiter
from core.rate_limit import init_rate_limiter

# FastAPI-Cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from core.redis import async_redis_client # Use shared async client

# Prometheus instrumentation
from prometheus_fastapi_instrumentator import Instrumentator
from core.monitoring import WS_CONNECTIONS  # Trigger metric registration

# route_engine imported lazily during startup
route_engine = None

logger = logging.getLogger("app")

from utils.metrics import ACTIVE_SESSIONS

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the FastAPI application."""
    ACTIVE_SESSIONS.set(1) # Base session for the API process itself
    # ensure required configuration exists (Supabase URL/key, database URL)
    try:
        Config.validate()
    except Exception as err:
        logger.critical(f"Configuration validation failed: {err}")
        raise

    logger.info("Starting RouteMaster API...")

    # quick Supabase connectivity check
    try:
        from supabase_client import supabase
        resp = supabase.from_("profiles").select("id").limit(1).execute()
        if hasattr(resp, "error") and resp.error:
            raise RuntimeError(resp.error)
        logger.info("Supabase connection verified.")
    except Exception as sup_err:
        logger.warning(f"Unable to verify Supabase connectivity: {sup_err}")

    try:
        # Initialize database schema
        await init_db()
        logger.info("Database initialized")

        # Initialize FastAPI-Cache
        FastAPICache.init(RedisBackend(async_redis_client), prefix="fastapi-cache")
        logger.info("FastAPI-Cache initialized with Redis.")

        # Initialize FastAPI-Limiter
        await init_rate_limiter()
        logger.info("FastAPI-Limiter initialized with Redis.")

        # Load the route engine graph into memory
        from database.session import SessionLocal as _SessionLocal
        from core.route_engine import route_engine as _route_engine
        global route_engine
        route_engine = _route_engine

        # Production initialization (Topic 1)
        # We call initialize() directly; background warmup task is now part of it
        try:
            logger.info("Starting RouteEngine production initialization...")
            await route_engine.initialize()
            logger.info("✅ RouteEngine initialized and major hubs verified.")
            
            # Risk 1: Verify Memory Usage
            try:
                import psutil
                process = psutil.Process()
                mem_info = process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                logger.info(f"📈 Post-Initialization Memory Usage: {rss_mb:.2f} MB")
                if rss_mb > 2048:
                    logger.warning(f"⚠️ HIGH MEMORY USAGE: {rss_mb:.2f} MB exceeds recommended 2GB limit.")
            except ImportError:
                logger.warning("psutil not installed; skipping memory verification.")
        except Exception as e:
            logger.critical(f"CRITICAL: RouteEngine failed to initialize: {e}")

        # prep station cache
        try:
            from services.station_service import StationService
            svc = StationService(_SessionLocal())
            total = svc.get_total_stations_count()
            logger.info(f"Station cache warmed with {total} stations.")
        except Exception as e:
            logger.warning(f"Failed to warm station cache: {e}")

        # Start workers
        start_reconciliation_worker()
        logger.info("Payment reconciliation worker initialized.")

        # Analytics
        if Config.KAFKA_ENABLE_EVENTS:
            from services.analytics_consumer import start_analytics_consumer
            asyncio.create_task(start_analytics_consumer())
            logger.info("Analytics consumer initialized.")

        # Position Broadcaster
        try:
            from services.realtime_ingestion.position_broadcaster import broadcaster
            asyncio.create_task(broadcaster.start())
            logger.info("✅ WebSocket Position Broadcaster initialized")
        except Exception as e:
            logger.warning(f"Position Broadcaster failed to start: {e}")

        # ETL Scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import httpx

        scheduler = AsyncIOScheduler()
        async def monthly_etl_job():
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "http://localhost:8000/api/admin/etl-sync",
                        params={"token": Config.ADMIN_API_TOKEN}
                    )
            except Exception as e:
                logger.error(f"Monthly ETL job failed: {e}")

        scheduler.add_job(monthly_etl_job, trigger=CronTrigger(day=1, hour=2), id="monthly_etl")
        scheduler.start()
        
        app.state.startup_complete = True
        yield
    finally:
        # Shutdown logic
        logger.info("Shutting down RouteMaster API...")
        stop_reconciliation_worker()
        await close_db()
        try:
            await FastAPICache.clear()
        except Exception:
            pass
        logger.info("Cleanup complete.")

# Get CORS configuration from environment
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://frontend:5173"
).split(",")

# Rate limit exceeded handler
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"code": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded", "timestamp": datetime.utcnow().isoformat()})


app = FastAPI(
    title="RouteMaster API",
    description="High-performance route optimization and booking platform",
    version="1.0.0",
    lifespan=lifespan
)

# Standard HTTPException handler that wraps detail in a consistent schema
@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    content = {
        "code": exc.detail if isinstance(exc.detail, str) else "ERROR",
        "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        "timestamp": datetime.utcnow().isoformat(),
    }
    return JSONResponse(status_code=exc.status_code, content=content)


# Generic exception handler
@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "timestamp": datetime.utcnow().isoformat()},
    )

# Mount Prometheus Instrumentator early so middleware is registered before startup
try:
    Instrumentator().instrument(app).expose(app)
    logger.info("Prometheus Instrumentator mounted at /metrics")
except Exception as ex:
    logger.warning(f"Prometheus instrumentation failed to initialize at module import: {ex}")

# Set up rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS with environment-based origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")

app.include_router(search.router)
app.include_router(routes.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(auth.router)
app.include_router(status.router)
app.include_router(sos.router)
app.include_router(flow.router)
app.include_router(websockets.router)
app.include_router(bookings.router)
app.include_router(realtime.router)
# Backwards-compatible stations endpoint
from api import stations as stations_api
app.include_router(stations_api.router)

from api import integrated_search
app.include_router(integrated_search.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "RouteMaster API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    """Blueprint-compliant health check."""
    return {
        "status": "ok",
        "service": "RouteMaster Backend",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/debug/engine")
async def engine_status():
    """Manual engine debug endpoint."""
    global route_engine
    if route_engine is None or not getattr(route_engine, 'current_snapshot', None):
        return {"status": "not_initialized"}

    snapshot = route_engine.current_snapshot
    return {
        "status": "running",
        "stops": len(snapshot.stop_cache),
        "trips": len(snapshot.trip_segments),
        "departures": len(snapshot.departures_by_stop),
        "hubs_initialized": hasattr(route_engine, 'hub_manager')
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=Config.ENVIRONMENT == "development",
    )
