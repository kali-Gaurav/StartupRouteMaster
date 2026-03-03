import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from database.session import init_db
from dependencies import get_route_engine
from services.multi_layer_cache import multi_layer_cache

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Databases and Caches
    logger.info("🚀 Starting Railway System...")
    await init_db()
    await multi_layer_cache.initialize()
    
    # Warm up route engine
    get_route_engine()
    
    yield
    # Shutdown
    logger.info("🛑 Shutting down Railway System...")

app = FastAPI(
    title="RouteMaster V2 API",
    description="High-performance Railway Search & Booking Engine",
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

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "database": "connected (Multi-DB)",
        "cache": "connected" if multi_layer_cache.redis else "disconnected"
    }

# --- Import Routers ---
# Note: These will be connected as we refactor API endpoints
# from api.v2 import search, booking, user

@app.get("/")
async def root():
    return {"message": "Welcome to RouteMaster V2 API Portal"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
