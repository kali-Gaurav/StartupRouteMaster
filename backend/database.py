from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.horizontal_shard import ShardedSession
import logging

from typing import Optional
from fastapi import Request

from backend.config import Config

logger = logging.getLogger(__name__)

# --- Database Engines ---
# Primary (write) database engine
engine_write = create_engine(
    Config.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=Config.ENVIRONMENT == "development",
)

# Read replica database engine (if configured)
engine_read = None
if Config.READ_DATABASE_URL:
    engine_read = create_engine(
        Config.READ_DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=Config.ENVIRONMENT == "development",
    )

# --- Custom Connection Routing ---
class RoutingSession(ShardedSession):
    """
    A SQLAlchemy session that routes connections to a read replica for read-only
    operations if a read replica is configured.
    """
    def _name_for_object(self, obj):
        # We don't need object-level sharding, so this method is simplified.
        # This determines which 'shard' (engine) an object belongs to.
        # For simplicity, we'll route based on the session's read_only flag.
        return 'reader' if getattr(self, '_read_only', False) and engine_read else 'writer'

    def _shard_chooser(self, mapper, instance, clause=None):
        if getattr(self, '_read_only', False) and engine_read:
            return 'reader'
        return 'writer'

    def _choose_conn_for_mapper(self, mapper, read_only=False, **kw):
        if read_only and engine_read:
            return self.get_bind(mapper, shard_id='reader', **kw)
        return self.get_bind(mapper, shard_id='writer', **kw)

    def get_bind(self, mapper=None, *, shard_id=None, **kw):
        if shard_id:
            if shard_id == 'reader':
                if engine_read:
                    return engine_read
                else:
                    logger.warning("Read replica requested but not configured, falling back to writer.")
                    return engine_write
            elif shard_id == 'writer':
                return engine_write
        # Fallback if no shard_id or special routing is determined
        return engine_write

    def connection(self, mapper=None, *, shard_id=None, **kw):
        if shard_id:
            return super().connection(mapper=mapper, shard_id=shard_id, **kw)
        
        # Determine if this connection should be read-only based on the session's flag
        if getattr(self, '_read_only', False) and engine_read:
            return super().connection(mapper=mapper, shard_id='reader', **kw)
        return super().connection(mapper=mapper, shard_id='writer', **kw)

# --- Session Factory ---
# Bind to both engines for the RoutingSession
SessionLocal = sessionmaker(
    class_=RoutingSession,
    autocommit=False,
    autoflush=False,
)
SessionLocal.configure(
    binds={'writer': engine_write, 'reader': engine_read or engine_write}
)

Base = declarative_base()

# --- Dependency to get a database session ---
def get_db(request: Optional[Request] = None):
    """
    Dependency to get a database session.
    Routes read-only requests to the read replica if available.
    """
    db = SessionLocal()
    # Check if the request method implies a read-only operation
    # FastAPI's Request object has a method attribute
    if request and request.method == "GET" and engine_read:
        db._read_only = True
        logger.debug("Using read replica for GET request.")
    else:
        db._read_only = False
        logger.debug("Using write database for non-GET or no-read-replica-configured request.")
        
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


async def init_db():
    """Initialize database schema."""
    try:
        # For init_db, we always use the write engine to create tables.
        Base.metadata.create_all(bind=engine_write)
        logger.info("Database tables created successfully on primary engine.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db():
    """Dispose database engines on shutdown."""
    if engine_write:
        engine_write.dispose()
        logger.info("Primary database engine disposed.")
    if engine_read:
        engine_read.dispose()
        logger.info("Read replica database engine disposed.")

# Wrap all database queries in try/except blocks
def safe_query(session: Session, query):
    """Execute a database query safely."""
    try:
        result = session.execute(query)
        return result
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise
