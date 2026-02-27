from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
import logging

from fastapi import Request

from .config import Config

logger = logging.getLogger(__name__)

# --- Database Engines ---
# Primary (write) database engine
# Since connectivity may fail (e.g. offline mode or unreachable host), we
# wrap creation in a helper that can fall back to an in-memory SQLite engine.

def _create_primary_engine():
    try:
        # Use DATABASE_URL from config which now handles OFFLINE_MODE logic
        url = Config.DATABASE_URL
        if not url:
            if Config.OFFLINE_MODE:
                logger.info("OFFLINE_MODE enabled with no DATABASE_URL; using in-memory SQLite.")
                return create_engine("sqlite:///:memory:", echo=Config.ENVIRONMENT == "development")
            else:
                raise RuntimeError("DATABASE_URL is not set and OFFLINE_MODE is false.")

        return create_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=Config.ENVIRONMENT == "development",
        )
    except Exception as e:
        if Config.OFFLINE_MODE:
            logger.warning(f"Unable to create primary database engine ({e}); falling back to SQLite in-memory.")
            return create_engine("sqlite:///:memory:", echo=Config.ENVIRONMENT == "development")
        else:
            logger.critical(f"DATABASE CONNECTION FAILURE: {e}")
            # In production-like environments, we want to fail fast if the primary DB is down
            raise e

engine_write = _create_primary_engine()

# Read replica database engine (if configured)
engine_read = None
if Config.READ_DATABASE_URL and not Config.OFFLINE_MODE:
    try:
        engine_read = create_engine(
            Config.READ_DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=Config.ENVIRONMENT == "development",
        )
    except Exception as e:
        logger.warning(f"Unable to create read-replica engine ({e}); continuing without replica.")
        engine_read = None

# --- Custom Connection Routing ---
class RoutingSession(Session):
    """Session subclass that routes to a read-replica for read-only work when
    available. This keeps behaviour simple and avoids the additional
    requirements that come with SQLAlchemy's horizontal sharding session.
    """

    def get_bind(self, mapper=None, **kw):
        # Optional explicit shard_id (kept for backward-compatibility).
        shard_id = kw.pop("shard_id", None)
        if shard_id == "reader":
            return engine_read if engine_read else engine_write
        if shard_id == "writer":
            return engine_write

        # Use session-level flag (set by dependency) to route reads to replica
        if getattr(self, "_read_only", False) and engine_read:
            return engine_read
        return engine_write

    def connection(self, mapper=None, **kw):
        # Allow explicit shard_id to be passed through to get_bind
        shard_id = kw.pop("shard_id", None)
        if shard_id:
            return super().connection(mapper=mapper, **{**kw, "shard_id": shard_id})

        if getattr(self, "_read_only", False) and engine_read:
            return super().connection(mapper=mapper)
        return super().connection(mapper=mapper)

# --- Session Factory ---
# Bind to both engines for the RoutingSession
SessionLocal = sessionmaker(
    class_=RoutingSession,
    autocommit=False,
    autoflush=False,
    # Bind the session factory to the primary write engine by default. The
    # RoutingSession.get_bind implementation will return the read-replica
    # when appropriate (db._read_only is set by the dependency).
    bind=engine_write,
)

# Backwards-compatibility alias expected by many modules/tests
engine = engine_write

Base = declarative_base()

# --- Dependency to get a database session ---
def get_db(request: Request = None):
    """Dependency to get a database session.
    Routes read-only requests to the read replica if available.
    Accepting a bare `Request` (possibly None) avoids confusing FastAPI's dependency analyzer
    when `typing.Optional[Request]` is present.
    """
    db = SessionLocal()
    # Check if the request method implies a read-only operation
    # FastAPI's Request object has a method attribute
    if request and getattr(request, "method", None) == "GET" and engine_read:
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
        # For init_db, ensure required Postgres extensions exist (pg_trgm for trigram indexes)
        # then create tables on the write engine.
        try:
            dialect = engine_write.dialect.name
        except Exception:
            dialect = ""

        if dialect == "postgresql":
            try:
                with engine_write.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                    logger.info("Ensured pg_trgm extension exists on primary database.")
            except Exception as e:
                # Log and continue; creating the extension may require elevated DB privileges
                logger.warning(f"Could not create pg_trgm extension: {e}")

        # Create all tables and indexes. 
        # Using a safer approach for existing databases with pre-existing indexes.
        try:
            if dialect == "sqlite":
                # For SQLite, we might not have SpatiaLite, so create_all might fail
                # on geometry columns. We'll try to catch that specifically.
                try:
                    Base.metadata.create_all(bind=engine_write)
                except Exception as e:
                    if "RecoverGeometryColumn" in str(e):
                        logger.warning("SpatiaLite functions not found. Skipping full schema creation. Ensure database exists.")
                    else:
                        raise e
            else:
                Base.metadata.create_all(bind=engine_write)
            logger.info("Database tables created/verified successfully on primary engine.")
        except Exception as sqlalchemy_error:
            if "already exists" in str(sqlalchemy_error).lower():
                logger.info("Some database objects already exist. Continuing as schema is partially or fully initialized.")
            else:
                raise sqlalchemy_error
    except Exception as e:
        # catch operational errors due to network/DNS
        from sqlalchemy.exc import OperationalError
        if isinstance(e, OperationalError):
            # treat unreachable database as acceptable if offline mode or DNS error
            errstr = str(e).lower()
            if Config.OFFLINE_MODE or "could not translate host name" in errstr:
                logger.warning("Database unreachable; switching to SQLite fallback.")
                # re-create engines using in-memory SQLite and retry once
                new_engine = create_engine("sqlite:///:memory:", echo=Config.ENVIRONMENT == "development")
                globals()['engine_write'] = new_engine
                globals()['engine_read'] = None
                SessionLocal.configure(bind=new_engine)
                globals()['engine'] = new_engine
                try:
                    Base.metadata.create_all(bind=new_engine)
                    logger.info("SQLite fallback schema created successfully.")
                    return
                except Exception as inner:
                    logger.error(f"SQLite fallback schema creation also failed: {inner}")
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
