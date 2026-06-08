"""
API module for RouteMaster (Modularized)
========================================

RouteMaster API organized by logical domain.
This module registers all sub-routers into the main application router.
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger("routemaster.api")

# Create main router
router = APIRouter()

# NOTE: V2 and V3 routers are registered directly by core/routing/__init__.py.
# Do NOT re-import them here — it causes database/models.py to load twice,
# triggering SQLAlchemy "Table already defined" crashes.

# Domain-specific Router Inclusions
try:
    from .search.search import router as search_router
    router.include_router(search_router, prefix="/search")
except ImportError as e:
    logger.warning(f"Search router import failed: {e}")

try:
    from .bookings.bookings import router as bookings_router
    router.include_router(bookings_router, prefix="/bookings")
except ImportError as e:
    logger.warning(f"Bookings router import failed: {e}")

try:
    from .auth.users import router as users_router
    router.include_router(users_router, prefix="/users")
except ImportError as e:
    logger.warning(f"Users router import failed: {e}")

try:
    from .auth.auth import router as auth_router
    router.include_router(auth_router, prefix="/auth")
except ImportError as e:
    logger.warning(f"Auth router import failed: {e}")

try:
    from .system.tasks import router as tasks_router
    router.include_router(tasks_router, prefix="/tasks")
except ImportError as e:
    logger.warning(f"Tasks router import failed: {e}")

try:
    from .safety.sathi import router as sathi_router
    router.include_router(sathi_router, prefix="/sathi")
except ImportError as e:
    logger.warning(f"Sathi router import failed: {e}")

try:
    from .safety.sos import router as sos_router
    router.include_router(sos_router, prefix="/sos")
except ImportError as e:
    logger.warning(f"SOS router import failed: {e}")

try:
    from .communication.chat import router as chat_router
    router.include_router(chat_router, prefix="/chat")
except ImportError as e:
    logger.warning(f"Chat router import failed: {e}")

try:
    from .payments.payments import router as payments_router
    router.include_router(payments_router, prefix="/payments")
except ImportError as e:
    logger.warning(f"Payments router import failed: {e}")

# ── Tier-1 Feature Routers ─────────────────────────────────────────────────
# Feature A: SSE Progressive Route Delivery
try:
    from .search_sse import router as sse_router
    router.include_router(sse_router)
    logger.info("✅ [FEATURE-A] SSE Progressive Route Delivery: ONLINE")
except ImportError as e:
    logger.warning(f"SSE router import failed: {e}")

# Feature D: Corridor Safety Bus Admin API
try:
    from core.route_engine.corridor_safety_bus import safety_admin_router
    if safety_admin_router:
        router.include_router(safety_admin_router)
        logger.info("✅ [FEATURE-D] Corridor Safety Bus Admin API: ONLINE")
except ImportError as e:
    logger.warning(f"Safety Bus admin router import failed: {e}")
