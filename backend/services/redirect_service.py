"""
Legacy redirect/partner service stub.

The system previously integrated with partner redirect/affiliate flows. Per
current requirements those integrations have been removed. This module keeps a
minimal API so imports elsewhere do not crash; all operations are no-ops and
explicitly disabled.
"""

import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class RedirectService:
    """Disabled redirect service. Methods return safe defaults and log calls."""

    def __init__(self):
        self.enabled = False
        # keep a minimal partners dict for introspection (empty)
        self.partners = {}

    def generate_redirect_url(self, *args, **kwargs) -> Tuple[Optional[str], Optional[str]]:
        logger.info("Redirect service disabled: generate_redirect_url called, returning (None, None)")
        return None, None

    def get_partner_commission_rate(self, partner: str) -> float:
        logger.debug("Redirect service disabled: get_partner_commission_rate called")
        return 0.0

    def get_partner_health(self, partner_name: str) -> str:
        logger.debug("Redirect service disabled: get_partner_health called")
        return "DISABLED"

    def find_healthy_alternative_partner(self, *args, **kwargs) -> Optional[str]:
        logger.debug("Redirect service disabled: find_healthy_alternative_partner called")
        return None

    def invalidate_redirect_cache(self, pattern: str = "*") -> bool:
        logger.debug("Redirect service disabled: invalidate_redirect_cache called")
        return False


# single exported instance for compatibility
redirect_service = RedirectService()
