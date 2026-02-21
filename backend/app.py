from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import structlog
from datetime import datetime

from slowapi.errors import RateLimitExceeded

from backend.database.config import Config
from backend.database import init_db, close_db
from backend.api import search, routes, payments, admin, chat, users, reviews, auth, status, sos, flow, websockets, bookings, realtime
from backend.utils.limiter import limiter

# FastAPI-Cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
import redis.asyncio as aioredis

# Prometheus instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

from backend.core.route_engine import route_engine
from backend.database import SessionLocal
from backend.worker import start_reconciliation_worker, stop_reconciliation_worker

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# Rate limit exceeded handler
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})

app = FastAPI(
    title="RouteMaster API",
    description="High-performance route optimization and booking platform",
    version="1.0.0",
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Allow frontend development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
from backend.api import stations as stations_api
app.include_router(stations_api.router)
# New integrated search with full journey reconstruction
from backend.api import integrated_search
app.include_router(integrated_search.router)


@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    logger.info("Starting RouteMaster API...")
    try:
        # Initialize database schema
        await init_db()
        logger.info("Database initialized")

        # Initialize FastAPI-Cache
        cache_redis = aioredis.from_url(Config.REDIS_URL, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(cache_redis), prefix="fastapi-cache")
        logger.info("FastAPI-Cache initialized with Redis.")

        # Load the route engine graph into memory (optionally in background to speed startup)
        from backend.database import SessionLocal as _SessionLocal
        from backend.core.route_engine import route_engine

        # Warm-up the route engine graph either synchronously or async based on config
        if Config.ROUTEENGINE_ASYNC_WARMUP:
            async def _warmup():
                db_w = _SessionLocal()
                try:
                    # use the public API; underlying implementation will manage snapshots
                    await route_engine.search_routes("NDLS", "MMCT", datetime.utcnow())
                finally:
                    db_w.close()
            import asyncio
            asyncio.create_task(_warmup())
            logger.info("RouteEngine warm-up scheduled in background (async warmup enabled).")
        else:
            db = _SessionLocal()
            try:
                # perform an initial dummy search to load graph into memory
                import asyncio
                asyncio.run(route_engine.search_routes("NDLS", "MMCT", datetime.utcnow()))
            finally:
                db.close()

        # Start the payment reconciliation worker
        start_reconciliation_worker()
        logger.info("Payment reconciliation worker initialized.")

        # Phase 3: Unified Intelligent System - Auto-detect and log features
        try:
            logger.info("")
            logger.info("=" * 70)
            logger.info("🚀 Phase 3: Unified Intelligent System Initialization")
            logger.info("=" * 70)

            # Route engine auto-detects features on initialization
            detected_mode = Config.get_mode()
            logger.info(f"📡 Detected Mode: {detected_mode}")
            logger.info(f"🔧 Feature Flags:")
            logger.info(f"   • OFFLINE_MODE: {Config.OFFLINE_MODE}")
            logger.info(f"   • REAL_TIME_ENABLED: {Config.REAL_TIME_ENABLED}")
            logger.info(f"🌐 Live API Configuration:")
            logger.info(f"   • LIVE_FARES_API: {'✅ Configured' if Config.LIVE_FARES_API else '❌ Not configured'}")
            logger.info(f"   • LIVE_DELAY_API: {'✅ Configured' if Config.LIVE_DELAY_API else '❌ Not configured'}")
            logger.info(f"   • LIVE_SEAT_API: {'✅ Configured' if Config.LIVE_SEAT_API else '❌ Not configured'}")
            logger.info(f"   • LIVE_BOOKING_API: {'✅ Configured' if Config.LIVE_BOOKING_API else '❌ Not configured'}")
            logger.info(f"📦 Data Provider Status: {'🟢 ONLINE' if detected_mode == 'ONLINE' else '🟡 HYBRID' if detected_mode == 'HYBRID' else '🔴 OFFLINE'}")

            # Log from route engine
            logger.info("")

        except Exception as e:
            logger.warning(f"Phase 3 feature detection had non-fatal error: {e}")

        # Advanced 4-Pipeline Architecture - Initialize pipeline system
        try:
            from backend.pipelines.system import initialize_pipelines
            if initialize_pipelines(Config):
                logger.info("✅ Advanced 4-Pipeline System initialized successfully")
            else:
                logger.warning("⚠️  Pipeline system initialization had issues, continuing with reduced capabilities")
        except Exception as e:
            logger.warning(f"Pipeline system initialization failed: {e}")

        # Start analytics consumer if events are enabled
        if Config.KAFKA_ENABLE_EVENTS:
            from backend.services.analytics_consumer import start_analytics_consumer
            import asyncio
            asyncio.create_task(start_analytics_consumer())
            logger.info("Analytics consumer initialized.")
        else:
            logger.info("Analytics consumer disabled (KAFKA_ENABLE_EVENTS=false)")

        # Start WebSocket Position Broadcaster (Phase 12)
        try:
            from backend.services.realtime_ingestion.position_broadcaster import broadcaster
            import asyncio
            asyncio.create_task(broadcaster.start())
            logger.info("✅ WebSocket Position Broadcaster initialized")
        except Exception as e:
            logger.warning(f"Position Broadcaster failed to start: {e}")

        # Set up monthly ETL scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import httpx

        scheduler = AsyncIOScheduler()

        async def monthly_etl_job():
            """Run monthly ETL sync job."""
            try:
                logger.info("Starting scheduled monthly ETL sync")
                # Call the ETL endpoint internally
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/api/admin/etl-sync",
                        params={"token": Config.ADMIN_API_TOKEN}
                    )
                    if response.status_code == 200:
                        logger.info("Monthly ETL sync completed successfully")
                    else:
                        logger.error(f"Monthly ETL sync failed: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Monthly ETL job failed: {e}")

        # Schedule ETL to run on the 1st of every month at 2 AM
        scheduler.add_job(
            monthly_etl_job,
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="monthly_etl",
            name="Monthly ETL Sync",
            max_instances=1,
            replace_existing=True
        )

        scheduler.start()
        logger.info("Monthly ETL scheduler initialized (runs 1st of each month at 2 AM)")

    except Exception as e:
        logger.error(f"Failed during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Close database on shutdown."""
    logger.info("Shutting down RouteMaster API...")
    # Stop the payment reconciliation worker
    stop_reconciliation_worker()
    logger.info("Payment reconciliation worker stopped.")
    await close_db()
    await FastAPICache.clear() # Clear cache on shutdown, optional
    logger.info("FastAPI-Cache cleared.")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "RouteMaster API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=Config.ENVIRONMENT == "development",
    )
