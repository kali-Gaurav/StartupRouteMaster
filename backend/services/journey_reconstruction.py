# Consolidated wrapper - actual implementation is in backend.core.route_engine
# This file maintained for backwards compatibility
from backend.core.route_engine import RouteEngine

# Provide a thin wrapper around RouteEngine so that older callers
# (such as SearchService) can continue to pass a database parameter even
# though the new RouteEngine no longer requires or uses it.

class JourneyReconstructionEngine:
    """Compatibility layer that mimics the old constructor signature.

    The original RouteEngine used to accept a ``db`` parameter which was
    ignored; new versions drop the dependency.  SearchService still passes a
    session, so we provide this wrapper to swallow the argument and delegate
    to the real engine.
    """

    def __init__(self, db=None, *args, **kwargs):
        # db is intentionally unused
        self._inner = RouteEngine(*args, **kwargs)

    def __getattr__(self, name):
        # delegate attribute access to the inner engine
        return getattr(self._inner, name)


__all__ = ["JourneyReconstructionEngine"]

