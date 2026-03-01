from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware
import logging
import time
from datetime import datetime
import os
import asyncio
from contextlib import asynccontextmanager

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app")

# --- APP INSTANCE ---
app = FastAPI(
    title="RouteMaster Production API",
    version="2.2.0",
    default_response_class=ORJSONResponse
)

# --- 1. TOP-LEVEL CORS (Must wrap everything) ---
origins = [
    "https://www.routemaster.online",
    "https://routemaster.online",
    "https://startuproutemaster-production.up.railway.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# --- 2. EXPLICIT PREFLIGHT HANDLER ---
@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    response = Response(status_code=200)
    origin = request.headers.get("origin")
    if origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = origins[0]
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# --- 3. RESILIENT LIFESPAN (Isolated Initializations) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 PRODUCTION STARTUP INITIATED")

    # A. Database Initialization
    try:
        from database import init_db
        await init_db()
        logger.info("✅ DB initialized")
    except Exception as e:
        logger.error(f"❌ DB init failed: {e}")

    # B. Redis & Caching
    try:
        from core.redis import async_redis_client
        from fastapi_cache import FastAPICache
        from fastapi_cache.backends.redis import RedisBackend
        FastAPICache.init(RedisBackend(async_redis_client), prefix="fastapi-cache")
        logger.info("✅ Cache initialized")
    except Exception as e:
        logger.error(f"❌ Cache initialization failed: {e}")

    # C. Rate Limiter
    try:
        from core.rate_limit import init_rate_limiter
        await init_rate_limiter()
        logger.info("✅ Rate limiter initialized")
    except Exception as e:
        logger.error(f"❌ Rate limiter failed: {e}")

    # D. RouteMaster Engine (Background Task)
    try:
        from core.route_engine import route_engine
        asyncio.create_task(route_engine.initialize())
        logger.info("✅ Route engine background task started")
    except Exception as e:
        logger.error(f"❌ Route engine failed to start: {e}")

    # E. Background Worker
    try:
        from worker import start_reconciliation_worker
        start_reconciliation_worker()
        logger.info("✅ Worker started")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")

    app.state.startup_complete = True
    yield

    # --- SHUTDOWN ---
    logger.info("🛑 SHUTDOWN INITIATED")
    try:
        from database import close_db
        from worker import stop_reconciliation_worker
        await close_db()
        stop_reconciliation_worker()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

app.router.lifespan_context = lifespan

# --- 4. MIDDLEWARE ---
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"💥 REQUEST CRASH: {request.method} {request.url.path} - {e} ({process_time:.2f}ms)")
        # Return valid JSON even on crash so CORS headers are preserved
        return JSONResponse(
            status_code=500, 
            content={"code": "INTERNAL_ERROR", "message": "The server encountered an error processing this request."}
        )

# --- 5. CORE ENDPOINTS ---
@app.get("/health")
async def health():
    return {"status": "healthy", "engines": "ready" if getattr(app.state, "startup_complete", False) else "initializing"}

@app.get("/ping")
async def ping():
    return {"status": "online", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {"app": "RouteMaster Production", "docs": "/docs"}

# --- 6. ROUTER MOUNTING (Lazy-ish) ---
from api import (
    search, routes, payments, admin, chat, users, 
    reviews, auth, status, sos, flow, websockets, 
    bookings, realtime, stations, integrated_search
)

app.include_router(search.router)
app.include_router(integrated_search.router)
app.include_router(routes.router)
app.include_router(stations.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(flow.router)
app.include_router(realtime.router)
app.include_router(websockets.router)
app.include_router(status.router)
app.include_router(chat.router)
app.include_router(reviews.router)
app.include_router(sos.router)
app.include_router(admin.router)

# --- 7. SERVER START ---
if __name__ == "__main__":
    import uvicorn
    # Important: Railway uses the PORT env var
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
