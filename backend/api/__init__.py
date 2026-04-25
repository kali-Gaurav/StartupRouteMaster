"""
API module for RouteMaster
"""
from fastapi import APIRouter

# Create main router
router = APIRouter()

# NOTE: V2 and V3 routers are registered directly by core/routing/__init__.py.
# Do NOT re-import them here — it causes database/models.py to load twice,
# triggering SQLAlchemy "Table already defined" crashes.


# Include individual route files
try:
    from .search import router as search_router
    router.include_router(search_router, prefix="/search")
except ImportError:
    pass

try:
    from .bookings import router as bookings_router
    router.include_router(bookings_router, prefix="/bookings")
except ImportError:
    pass

try:
    from .users import router as users_router
    router.include_router(users_router, prefix="/users")
except ImportError:
    pass

try:
    from .auth import router as auth_router
    router.include_router(auth_router, prefix="/auth")
except ImportError:
    pass


# Include tasks router
try:
    from .tasks import router as tasks_router
    router.include_router(tasks_router, prefix="/tasks")
except ImportError:
    pass


# Include Sathi router
try:
    from .sathi import router as sathi_router
    router.include_router(sathi_router, prefix="/sathi")
except ImportError as e:
    print(f"Sathi router import failed: {e}")
    pass