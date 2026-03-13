import logging
import httpx
from typing import Optional, Dict, Any
from database.config import Config

logger = logging.getLogger(__name__)

class PNRStatusService:
    """Task 2.7: Fetches live PNR status from external providers."""

    def __init__(self):
        self.api_key = Config.RAPIDAPI_KEY
        self.api_host = Config.RAPIDAPI_HOST
        self.base_url = f"https://{self.api_host}/api/v3/getPNRStatus"

    async def get_status(self, pnr: str) -> Dict[str, Any]:
        """Fetch status for a 10-digit PNR."""
        if not pnr or len(pnr) != 10:
            return {"success": False, "message": "Invalid PNR format. Mission aborted."}

        # Task 7.1: Aggressive Caching (Check Redis first)
        # (Skipping Redis implementation for this surgical step to ensure reliability)

        if not self.api_key:
            # Safe Fallback for offline/dev
            return {
                "success": True,
                "pnr": pnr,
                "status": "CNF",
                "seat": "B1, 24 (Lower)",
                "train": "12626 - KERALA EXPRESS",
                "message": "Protocol Safe: Mock data returned in Dev Mode."
            }

        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.base_url, params={"pnrNumber": pnr}, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status"):
                        return {
                            "success": True,
                            "pnr": pnr,
                            "status": data.get("data", {}).get("currentStatus"),
                            "train": data.get("data", {}).get("trainName"),
                            "message": "Live telemetry acquired."
                        }
                    else:
                        return {"success": False, "message": data.get("message", "Provider returned status False.")}
                return {"success": False, "message": f"Provider error: {resp.status_code}"}
        except Exception as e:
            logger.error(f"PNR fetch failed: {e}")
            return {"success": False, "message": "Neural link timeout. Provider unreachable."}

pnr_status_service = PNRStatusService()
