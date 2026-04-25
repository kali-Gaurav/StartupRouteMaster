"""
Hardened Logger: Structured logging wrapper for production services.
"""
import logging
import json
from typing import Any, Optional, Dict


class HardenedLogger:
    """
    Structured logger that supports both plain string and event+context logging.
    Usage:
        logger = HardenedLogger("AUTH_SERVICE")
        logger.info("OTP_SENT_SUCCESS", {"contact": "+91..."})
        logger.warning("Rate limit triggered")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _format(self, event: str, context: Optional[Dict[str, Any]] = None) -> str:
        if context:
            safe_ctx = {k: str(v)[:200] for k, v in context.items()}
            return f"[{event}] {json.dumps(safe_ctx, default=str)}"
        return event

    def info(self, event: str, context: Optional[Dict[str, Any]] = None):
        self._logger.info(self._format(event, context))

    def warning(self, event: str, context: Optional[Dict[str, Any]] = None):
        self._logger.warning(self._format(event, context))

    def error(self, event: str, context: Optional[Dict[str, Any]] = None):
        self._logger.error(self._format(event, context))

    def debug(self, event: str, context: Optional[Dict[str, Any]] = None):
        self._logger.debug(self._format(event, context))

    def critical(self, event: str, context: Optional[Dict[str, Any]] = None):
        self._logger.critical(self._format(event, context))
