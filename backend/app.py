from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import structlog

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.config import Config
from backend.database import init_db, close_db
from backend.api import search, routes, payments, admin, chat, users, reviews, auth, status, sos, flow

# Prometheus instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

from backend.services.route_engine import route_engine
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

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

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
# Backwards-compatible stations endpoint
from backend.api import stations as stations_api
app.include_router(stations_api.router)


@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    logger.info("Starting RouteMaster API...")
    try:
        # Initialize database schema
        await init_db()
        logger.info("Database initialized")

        # Load the route engine graph into memory
        db = SessionLocal()
        try:
            route_engine.load_graph_from_db(db)
        finally:
            db.close()

        # Start the payment reconciliation worker
        start_reconciliation_worker()
        logger.info("Payment reconciliation worker initialized.")

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
