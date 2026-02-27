import logging
import requests
from typing import Optional, Dict

from database.config import Config

logger = logging.getLogger(__name__)


class FareService:
    """Calls the Rapid IRCTC fare enquiry endpoint."""

    def __init__(self, config: Config = Config):
        self.url = "https://irctc1.p.rapidapi.com/api/v3/getFare"
        self.enabled = getattr(config, "ENABLE_FARE_VERIFICATION", False) and bool(config.RAPIDAPI_KEY)
        self.headers = {
            "x-rapidapi-key": getattr(config, "RAPIDAPI_KEY", ""),
            "x-rapidapi-host": getattr(config, "RAPIDAPI_HOST", "irctc1.p.rapidapi.com")
        }
        self.timeout = getattr(config, "LIVE_API_TIMEOUT_MS", 10)

    def get_fare(
        self,
        train_no: str,
        from_station: str,
        to_station: str,
        class_code: str,
        quota: str = "GN",
        date: str = ""
    ) -> Optional[Dict]:
        if not self.enabled or not train_no:
            logger.debug("Fare lookup disabled or missing train number")
            return None

        params = {
            "trainNo": train_no,
            "fromStationCode": from_station,
            "toStationCode": to_station,
            "class": class_code,
            "quota": quota,
            "date": date
        }

        try:
            response = requests.get(self.url, headers=self.headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            return {
                "source": "rapidapi",
                "success": payload.get("success", True),
                "quota": quota,
                "class": class_code,
                "data": payload
            }
        except Exception as exc:
            logger.warning("Fare API failed for %s %s-%s: %s", train_no, from_station, to_station, exc)
            return {"source": "rapidapi", "success": False, "error": str(exc)}
