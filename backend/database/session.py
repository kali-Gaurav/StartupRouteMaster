from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os

logger = logging.getLogger(__name__)

# Optimization for SQLite
def _enable_sqlite_optimizations(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# --- Engines ---
user_db_path = "sqlite:///backend/database/user_store.db"
transit_db_path = "sqlite:///backend/database/transit_graph.db"

engine_user = create_engine(user_db_path, connect_args={"check_same_thread": False})
engine_transit = create_engine(transit_db_path, connect_args={"check_same_thread": False})

event.listen(engine_user, "connect", _enable_sqlite_optimizations)
event.listen(engine_transit, "connect", _enable_sqlite_optimizations)

# --- Metadata & Bases ---
# We use two separate bases so tables don't leak into the wrong database
UserBase = declarative_base()
TransitBase = declarative_base()

# Legacy compatibility
Base = UserBase 

# --- Session Factories ---
SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)
SessionTransit = sessionmaker(autocommit=False, autoflush=False, bind=engine_transit)

# Defaults
SessionLocal = SessionUser
engine = engine_user

def get_db():
    db = SessionUser()
    try: yield db
    finally: db.close()

def get_transit_db():
    db = SessionTransit()
    try: yield db
    finally: db.close()

async def init_db():
    """Create tables in their respective physical databases."""
    # This will only create tables inheriting from UserBase in user_store.db
    UserBase.metadata.create_all(bind=engine_user)
    # This will only create tables inheriting from TransitBase in transit_graph.db
    TransitBase.metadata.create_all(bind=engine_transit)
    logger.info("🚀 Dual-Database Physical Split Complete.")

def get_source_connection():
    import sqlite3
    db_path = os.path.join(os.getcwd(), 'backend', 'database', 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
