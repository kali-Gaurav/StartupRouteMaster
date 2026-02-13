from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import Config
from database import init_db, close_db
from api import search, routes, payments, admin, chat, users, reviews, auth, status, sos, flow

from services.route_engine import route_engine
from database import SessionLocal

logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RouteMaster API",
    description="High-performance route optimization and booking platform",
    version="1.0.0",
)

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

    except Exception as e:
        logger.error(f"Failed during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Close database on shutdown."""
    logger.info("Shutting down RouteMaster API...")
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
