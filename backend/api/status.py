from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from datetime import datetime

from database.session import get_async_db
from database.config import Config

# Root APIRouter - used for shared/common status logic if needed.
# [Task 1.15] Re-mapping for Frontend V7 Compatibility
router = APIRouter(prefix="/status", tags=["status"])
logger = logging.getLogger(__name__)

@router.get("/health/live")
async def health_live():
    """
    [Task 5.2] Consolidated Frontend Liveness Probe.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.0",
        "mode": Config.get_mode()
    }

@router.get("/health/ready")
async def health_ready():
    """
    Ready check - are all critical services ready?
    """
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.state import SystemState
    return {
        "status": "ready" if nexus_boot.state == SystemState.READY else "degraded",
        "timestamp": datetime.utcnow().isoformat()
    }
