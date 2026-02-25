"""Simple helper to track last successful external API interaction.

Rather than pinging third-party services on every health check we remember the
last time a live API call succeeded.  Health endpoints use this timestamp to
determine whether the external API component is ``ok`` or ``stale``.
"""
from datetime import datetime, timedelta
from typing import Optional

# time of last successful call (UTC)
_last_success: Optional[datetime] = None

# refresh threshold (e.g. 5 minutes).  If the last success is older than this the
# component is considered degraded.  Can be tweaked via config later if needed.
STALE_THRESHOLD = timedelta(minutes=5)


def record_success(timestamp: Optional[datetime] = None) -> None:
    """Mark that an external API call succeeded at ``timestamp`` (default now)."""
    global _last_success
    _last_success = timestamp or datetime.utcnow()


def get_last_success() -> Optional[datetime]:
    """Return the last successful timestamp, or ``None`` if never seen."""
    return _last_success


def is_fresh() -> bool:
    """Return ``True`` if the last success is within the freshness threshold."""
    if _last_success is None:
        return False
    return datetime.utcnow() - _last_success <= STALE_THRESHOLD
