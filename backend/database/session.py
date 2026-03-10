from sqlalchemy import create_engine, event, MetaData, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
import os

from .config import Config

logger = logging.getLogger(__name__)

_BASE_DIR = Config.BASE_DIR

# --- Metadata & Bases (Define these FIRST before engines) ---
UserBase = declarative_base()
TransitBase = declarative_base()
Base = UserBase

# --- Engines (Legacy Sync) ---
user_db_url_sync = Config.GET_SQLALCHEMY_URL("user", is_async=False)
transit_db_url_sync = Config.GET_SQLALCHEMY_URL("transit", is_async=False)

engine_user = create_engine(user_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in user_db_url_sync else {})
engine_transit = create_engine(transit_db_url_sync, connect_args={"check_same_thread": False} if "sqlite" in transit_db_url_sync else {})

# --- Engines (Modern Async) ---
user_db_url_async = Config.GET_SQLALCHEMY_URL("user", is_async=True)
transit_db_url_async = Config.GET_SQLALCHEMY_URL("transit", is_async=True)

async_engine_user = create_async_engine(user_db_url_async, echo=False) # Echoing off for cleaner logs
async_engine_transit = create_async_engine(transit_db_url_async, echo=False)

# --- Session Factories (Sync) ---
SessionUser = sessionmaker(autocommit=False, autoflush=False, bind=engine_user)
SessionTransit = sessionmaker(autocommit=False, autoflush=False, bind=engine_transit)

# --- Session Factories (Async) ---
AsyncSessionUser = sessionmaker(
    async_engine_user, class_=AsyncSession, expire_on_commit=False
)
AsyncSessionTransit = sessionmaker(
    async_engine_transit, class_=AsyncSession, expire_on_commit=False
)

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

async def get_async_db():
    async with AsyncSessionUser() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_transit_db():
    async with AsyncSessionTransit() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """
    ROOT FIX: Force model discovery by importing models.py
    Ensures metadata is populated before create_all is called.
    """
    from . import models # This triggers model registration on TransitBase/UserBase
    
    async with async_engine_user.begin() as conn:
        await conn.run_sync(UserBase.metadata.create_all)
    
    async with async_engine_transit.begin() as conn:
        await conn.run_sync(TransitBase.metadata.create_all)
        
    logger.info("✅ Database physical tables initialized/verified.")

def get_source_connection():
    import sqlite3
    db_path = os.path.join(_BASE_DIR, 'railway_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
