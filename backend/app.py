from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware
import logging
import time
from datetime import datetime
import os
import asyncio
from contextlib import asynccontextmanager

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")

from slowapi.errors import RateLimitExceeded
from worker import start_reconciliation_worker, stop_reconciliation_worker
from database.config import Config
from database import init_db, close_db

# --- IMPORT ALL ROUTERS ---
from api import (
    search, routes, payments, admin, chat, users, 
    reviews, auth, status, sos, flow, websockets, 
    bookings, realtime, stations, integrated_search
)

from utils.limiter import limiter
from core.rate_limit import init_rate_limiter

# FastAPI-Cache & Redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from core.redis import async_redis_client

# Monitoring & Metrics
from prometheus_fastapi_instrumentator import Instrumentator
from core.monitoring import WS_CONNECTIONS
from utils.metrics import ACTIVE_SESSIONS

# Route Engine (Lazily initialized)
route_engine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Manager.
    Handles startup and shutdown of all production services.
    """
    ACTIVE_SESSIONS.set(1)
    
    # 1. VALIDATE CONFIGURATION (Railway/Supabase/Redis)
    try:
        Config.validate()
        logger.info("✅ Production Configuration Validated.")
    except Exception as err:
        logger.critical(f"❌ Configuration Error: {err}")
        if Config.ENVIRONMENT == "production":
            raise SystemExit(1)

    # 2. INITIALIZE DATABASE (Railway Postgres)
    try:
        await init_db()
        logger.info("✅ Railway Database Connected & Schema Synchronized.")
    except Exception as db_err:
        logger.error(f"❌ Database Initialization Failed: {db_err}")

    # 3. INITIALIZE REDIS SERVICES (Upstash)
    try:
        # FastAPI Response Caching
        FastAPICache.init(RedisBackend(async_redis_client), prefix="fastapi-cache")
        # Rate Limiting
        await init_rate_limiter()
        logger.info("✅ Redis Services (Cache & Limiter) Active.")
    except Exception as redis_err:
        logger.error(f"❌ Redis Initialization Failed: {redis_err}")

    # 4. INITIALIZE CORE ENGINES (RouteMaster & Station Search)
    from core.route_engine import route_engine as _route_engine
    from services.station_search_service import station_search_engine as _station_search_engine
    global route_engine
    route_engine = _route_engine

    async def engine_warmup():
        try:
            logger.info("🧠 Initializing RouteMaster Engine (Graph + Models)...")
            _station_search_engine._ensure_initialized()
            await route_engine.initialize()
            logger.info("🚀 RouteMaster Engine Ready for High-Performance Routing.")
            
            # Post-startup warmup tasks
            from services.station_service import StationService
            from database.session import SessionLocal
            db = SessionLocal()
            try:
                total_stations = StationService(db).get_total_stations_count()
                logger.info(f"🚉 Station Index Ready: {total_stations} stations indexed.")
            finally: db.close()
            
            # Start background pre-warming
            asyncio.create_task(prewarm_popular_routes())
        except Exception as e:
            logger.error(f"❌ Engine Warmup Failed: {e}")

    asyncio.create_task(engine_warmup())

    # 5. START BACKGROUND WORKERS
    start_reconciliation_worker()
    from services.realtime_ingestion.position_broadcaster import broadcaster
    asyncio.create_task(broadcaster.start())
    logger.info("✅ Background Workers & Broadcasters Started.")

    # 6. SUPABASE CONNECTIVITY VERIFICATION
    try:
        from supabase_client import supabase
        supabase.from_("profiles").select("id").limit(1).execute()
        logger.info("✅ Supabase Auth & Profiles Verified.")
    except Exception as sup_err:
        logger.warning(f"⚠️ Supabase Connectivity Warning: {sup_err}")

    app.state.startup_complete = True
    yield
    
    # --- SHUTDOWN SEQUENCE ---
    logger.info("🛑 Shutting down RouteMaster API...")
    
    # Close external API sessions
    from services.realtime_ingestion.live_status_service import LiveStatusService
    from services.seat_verification import SeatVerificationService
    await LiveStatusService.close_session()
    await SeatVerificationService.close_session()
    
    stop_reconciliation_worker()
    await close_db()
    logger.info("👋 Cleanup Complete. System Offline.")

async def prewarm_popular_routes():
    """Warms up L1 cache for the most frequent searches."""
    await asyncio.sleep(60) # Wait for engine to be fully ready
    popular = [("NDLS", "BCT"), ("BCT", "NDLS"), ("NDLS", "SBC"), ("MAS", "SBC")]
    from api.integrated_search import unified_search
    from schemas import SearchRequest
    from database.session import SessionLocal
    
    while True:
        target_date = datetime.now().date().isoformat()
        logger.info(f"🔥 Pre-warming L1 Cache for {len(popular)} major routes...")
        for src, dst in popular:
            db = SessionLocal()
            try:
                req = SearchRequest(source=src, destination=dst, date=target_date)
                await unified_search(req, db)
            except Exception: pass
            finally: db.close()
        await asyncio.sleep(3600) # Re-warm every hour

# --- APP INSTANCE ---

app = FastAPI(
    title="RouteMaster Production API",
    description="Intelligent Railway Route Optimization & Booking Platform",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=ORJSONResponse
)

# --- MIDDLEWARE ---

# 1. GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. CORS (Production Grade)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.routemaster.online",
        "https://routemaster.online",
        "https://startuproutemaster-production.up.railway.app"
        
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Set-Cookie",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Origin",
        "Authorization",
        "X-Requested-With",
        "X-Admin-Token"
    ],
    expose_headers=["*"],
    max_age=3600,
)

# 3. Request/Response Logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    method = request.method
    
    logger.info(f"🚀 INCOMING: {method} {path}")
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(f"✅ OUTGOING: {method} {path} - Status: {response.status_code} ({process_time:.2f}ms)")
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ CRITICAL ERROR: {method} {path} - {str(e)} ({process_time:.2f}ms)")
        raise

# --- EXCEPTION HANDLERS ---

@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "API_ERROR", 
            "message": str(exc.detail), 
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429, 
        content={
            "code": "RATE_LIMIT_EXCEEDED", 
            "message": "Too many requests. Please slow down.", 
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# --- INSTRUMENTATION ---
try:
    Instrumentator().instrument(app).expose(app)
except Exception: pass

# --- ROUTER MOUNTING ---

# Search & Routing
app.include_router(search.router)
app.include_router(integrated_search.router)
app.include_router(routes.router)
app.include_router(stations.router)

# Auth & Users
app.include_router(auth.router)
app.include_router(users.router)

# Bookings & Payments
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(flow.router)

# Real-time & Sockets
app.include_router(realtime.router)
app.include_router(websockets.router)
app.include_router(status.router)

# Auxiliary Services
app.include_router(chat.router)
app.include_router(reviews.router)
app.include_router(sos.router)
app.include_router(admin.router)

# --- CORE ENDPOINTS ---

@app.get("/ping")
async def ping():
    """Minimal latency check."""
    return {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "mode": Config.get_mode()
    }

@app.get("/")
async def health_summary():
    """Detailed system health overview."""
    from services.multi_layer_cache import multi_layer_cache
    cache_healthy = await multi_layer_cache.health_check()
    
    return {
        "app": "RouteMaster Production API",
        "version": "2.0.0",
        "engines": {
            "routemaster": "ready" if app.state.startup_complete else "initializing",
            "cache": "connected" if cache_healthy else "degraded"
        },
        "docs": "/docs"
    }

# --- SERVER START ---

if __name__ == "__main__":
    import uvicorn
    # Production uvicorn config
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False, 
        workers=1, # Shared engine graph works best with 1 worker or sharded graph
        log_level="info"
    )
