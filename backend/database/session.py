from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os

logger = logging.getLogger(__name__)
# Optimization for SQLite
def _enable_sqlite_optimizations(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # Suggestion #21: Query Only for Transit in Production
    db_name = str(dbapi_connection)
    if "transit_graph.db" in db_name:
        # Suggestion #22: Memory Mapping (2GB)
        cursor.execute("PRAGMA mmap_size = 2147483648")
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=OFF")
    else:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")

    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# --- Engines ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
user_db_path = f"sqlite:///{os.path.join(BASE_DIR, 'user_store.db')}"
transit_db_path = f"sqlite:///{os.path.join(BASE_DIR, 'transit_graph.db')}"

engine_user = create_engine(user_db_path, connect_args={"check_same_thread": False})
engine_transit = create_engine(transit_db_path, connect_args={"check_same_thread": False})

event.listen(engine_user, "connect", _enable_sqlite_optimizations)
event.listen(engine_transit, "connect", _enable_sqlite_optimizations)

# Specific naming for internal use
engine_write = engine_user
engine_read = engine_transit

# --- Metadata & Bases ---
UserBase = declarative_base()
TransitBase = declarative_base()
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
    from .models import User, Stop 
    # Force TransitBase to use engine_transit
    UserBase.metadata.create_all(bind=engine_user)
    TransitBase.metadata.create_all(bind=engine_transit)
    logger.info("Dual-Database physical tables verified.")

def get_source_connection():
    import sqlite3
    db_path = os.path.join(BASE_DIR, 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
