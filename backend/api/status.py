from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from datetime import datetime

from database.session import get_async_db
from database.config import Config

# Root APIRouter - used for shared/common status logic if needed.
# But we moved the primary /api/health and /api/stats to app.py for speed.
router = APIRouter(tags=["status"])
logger = logging.getLogger(__name__)

# We leave this empty or add specific internal status sub-routes if needed later.
# Primary health checks are handled in app.py to avoid import overhead.
