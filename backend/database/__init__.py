# database package initialization
# Optimized for modular architecture

from .infrastructure.session import (
    SessionUser, SessionTransit, SessionAuth, SessionLocal, SessionRead,
    AsyncSessionUser, AsyncSessionTransit, AsyncSessionAuth, AsyncSessionRead,
    get_db, get_transit_db, get_async_db, get_async_transit_db,
    initialize_database_pools, database_service
)
from .infrastructure.base import Base, UserBase, TransitBase
from .infrastructure.config import Config

# Re-export models for convenience
from .models import *
