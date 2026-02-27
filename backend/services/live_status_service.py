import logging
import requests
import json
from typing import Optional, Dict, Any

from database.config import Config
from services.realtime_ingestion.api_client import RappidAPIClient
from core.redis import redis_client

logger = logging.getLogger(__name__)


class LiveStatusService:
    """Fetches live running status from Rappid or RapidAPI fallback."""

    def __init__(self, config: Config = Config):
        self.config = config
        self.rappid_client = RappidAPIClient(cache_enabled=True)
        self.rapid_url = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"
        self.rapid_enabled = bool(config.RAPIDAPI_KEY)
        self.rapid_headers = {
            "x-rapidapi-key": getattr(config, "RAPIDAPI_KEY", ""),
            "x-rapidapi-host": getattr(config, "RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
        }
        self.timeout = getattr(config, "LIVE_API_TIMEOUT_MS", 10)

    def get_live_status(self, train_no: str) -> Optional[Dict[str, Any]]:
        """
        Get live status prioritizing Rappid API (cheaper/faster), 
        falling back to RapidAPI if needed.
        """
        if not train_no:
            return None

        status_data = None

        # 1. Try Rappid API first
        try:
            rappid_data = self.rappid_client.fetch_train_status(train_no)
            if rappid_data and rappid_data.get("success"):
                logger.info(f"✓ Live status from Rappid for {train_no}")
                status_data = {
                    "source": "rappid",
                    "success": True,
                    "train_no": train_no,
                    "train_name": rappid_data.get("train_name"),
                    "message": rappid_data.get("message"),
                    "updated_time": rappid_data.get("updated_time"),
                    "stations": rappid_data.get("data", []),
                }
        except Exception as e:
            logger.warning(f"Rappid status failed for {train_no}: {e}")

        # 2. Fallback to RapidAPI
        if not status_data and self.rapid_enabled:
            try:
                logger.info(f"📡 Falling back to RapidAPI for train {train_no}...")
                params = {"trainNo": train_no, "startDay": "0"}
                resp = requests.get(
                    self.rapid_url, 
                    headers=self.rapid_headers, 
                    params=params, 
                    timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                
                if data.get("success"):
                    status_data = {
                        "source": "rapidapi",
                        "success": True,
                        "train_no": train_no,
                        "data": data.get("data")
                    }
            except Exception as e:
                logger.error(f"RapidAPI fallback failed for {train_no}: {e}")

        # --- PUB/SUB BROADCAST ---
        if status_data and status_data.get("success"):
            try:
                # Publish update to Redis for WebSocket clients
                channel = f"train_position:{train_no}"
                redis_client.publish(channel, json.dumps(status_data))
                
                # Cache the last known position
                cache_key = f"pos:last:{train_no}"
                redis_client.setex(cache_key, 300, json.dumps(status_data))
                
                logger.debug(f"Broadcasted live status for {train_no} to {channel}")
            except Exception as pe:
                logger.warning(f"Failed to broadcast live status: {pe}")

        return status_data or {"source": "live-status", "success": False, "message": "All live status providers failed"}
