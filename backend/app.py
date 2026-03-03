import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from database.session import init_db
from dependencies import get_route_engine
from services.multi_layer_cache import multi_layer_cache
from database.config import Config
from core.middleware.observability import ObservabilityMiddleware

# --- Import V2 Routers ---
from api.v2 import search, debug, admin, live, user, booking

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting RouteMaster V2 Production Gateway...")
    await init_db()
    await multi_layer_cache.initialize()
    
    # Warm up route engine
    logger.info("📡 Warming up routing graph...")
    get_route_engine()
    
    yield
    # Shutdown
    logger.info("🛑 Shutting down Gateway...")

app = FastAPI(
    title="RouteMaster V2 API",
    description="Unified Railway Intelligence Gateway (Search, Real-time, Analytics, Auth Sync)",
    version="2.5.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Suggestion #19: Latency Tracking
app.add_middleware(ObservabilityMiddleware)

# Standard Error Handler
@app.exception_handler(Exception)
async def unified_exception_handler(request: Request, exc: Exception):
    logger.error(f"UNHANDLED ERROR: {exc}", exc_info=True)
    return {
        "error": True,
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "A critical system error occurred.",
        "detail": str(exc) if Config.DEBUG else "Please contact support."
    }

# --- Register Routers ---
app.include_router(search.router, prefix="/api/v2")
app.include_router(live.router, prefix="/api/v2")
app.include_router(user.router, prefix="/api/v2")
app.include_router(booking.router, prefix="/api/v2")
app.include_router(debug.router, prefix="/api/v2")
app.include_router(admin.router, prefix="/api/v2")

@app.get("/admin/dashboard", tags=["Internal"])
async def serve_dashboard():
    from fastapi.responses import FileResponse
    return FileResponse("monitoring/dashboard.html")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "db_mode": "Local SQLite (Physical Split)",
        "cache": "connected" if multi_layer_cache.redis else "disconnected",
        "version": "2.5.0"
    }

@app.get("/")
async def root():
    return {"message": "Welcome to RouteMaster V2 API Portal. Use /docs for documentation."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=Config.ENVIRONMENT == "development")
