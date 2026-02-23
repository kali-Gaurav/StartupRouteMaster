import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Use DATABASE_URL env var for Postgres in production, fallback to SQLite for dev.
DATABASE_URL = os.getenv("RMA_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite:///./backend/database/transit_graph.db"

# SQLite needs a special connect_arg; other DBs do not.
if DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tables should be created via migrations or explicit setup, not on module import
# Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
