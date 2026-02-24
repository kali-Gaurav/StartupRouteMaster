import logging
import requests
from typing import Optional

from backend.config import Config

logger = logging.getLogger(__name__)


class LiveStatusService:
    """Fetches live running status from the Rappid endpoint."""

    def __init__(self, config: Config = Config):
        self.base_url = getattr(config, "LIVE_STATUS_BASE_URL", "")
        self.enabled = getattr(config, "ENABLE_LIVE_STATUS", False) and bool(self.base_url)
        self.timeout = getattr(config, "LIVE_API_TIMEOUT_MS", 8)

    def get_live_status(self, train_no: str) -> Optional[dict]:
        if not self.enabled or not train_no:
            logger.debug("Live status lookup disabled or missing train number")
            return None

        try:
            resp = requests.get(
                self.base_url,
                params={"train_no": train_no},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                message = data.get("message") or "Live status API returned failure"
                logger.warning("Live status API returned failure for %s: %s", train_no, message)
                return {"source": "live-status", "success": False, "message": message}

            return {
                "source": "live-status",
                "success": True,
                "train_name": data.get("train_name"),
                "message": data.get("message"),
                "updated_time": data.get("updated_time"),
                "stations": data.get("data", []),
            }
        except Exception as exc:
            logger.warning("Live status lookup failed for %s: %s", train_no, exc)
            return {"source": "live-status", "success": False, "error": str(exc)}
