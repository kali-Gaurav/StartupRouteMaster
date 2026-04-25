from sqlalchemy.orm import Session
import logging
import httpx
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from database.config import Config

from core.resilience import circuit_manager, CircuitConfig, CircuitOpenError
from core.retry import retry, RETRY_POLICY_EXTERNAL_API

logger = logging.getLogger(__name__)

# Create circuit breaker for PNR service
PNR_BREAKER = circuit_manager.get_or_create(
    "pnr_service",
    CircuitConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
        half_open_max_calls=2
    )
)


class PNRStatusService:
    """Task 2.7: Fetches live PNR status from external providers with resilience."""

    def __init__(self):
        self.api_key = Config.RAPIDAPI_KEY
        self.api_host = Config.RAPIDAPI_HOST
        self.base_url = f"https://{self.api_host}/api/v3/getPNRStatus"
        
        # Local cache for PNR status
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 60  # 1 minute cache for live data

    def _get_cache_key(self, pnr: str) -> str:
        return f"pnr:{pnr}"

    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached PNR status is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    async def get_status(
        self, 
        pnr: str, 
        user_id: Optional[str] = None, 
        db: Optional[Session] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch status for a 10-digit PNR.
        Automatic Vault Integration [Task 4.7] for sensitive results.
        """
        if not pnr or len(pnr) != 10:
            return {"success": False, "message": "Invalid PNR format. Mission aborted."}

        cache_key = self._get_cache_key(pnr)
        
        # Check cache first (unless bypassed)
        if not bypass_cache and pnr in self._cache and self._is_cache_valid(self._cache[pnr]):
            cached = self._cache[pnr]
            logger.debug(f"📦 Cache hit for PNR {pnr}")
            return cached

        # Safe Fallback for offline/dev
        if not self.api_key:
            result = {
                "success": True,
                "pnr": pnr,
                "status": "CNF",
                "seat": "B1, 24 (Lower)",
                "train": "12626 - KERALA EXPRESS",
                "message": "Protocol Safe: Mock data returned in Dev Mode.",
                "cached_at": datetime.utcnow().isoformat()
            }
        else:
            try:
                # Execute through circuit breaker with retry
                result = await PNR_BREAKER.execute(
                    self._fetch_live_status,
                    pnr
                )
            except CircuitOpenError as cb_err:
                logger.error(f"Circuit breaker open for PNR service: {cb_err}")
                return {
                    "success": False, 
                    "message": "PNR service temporarily unavailable. Please try again shortly.",
                    "error_code": "SERVICE_UNAVAILABLE"
                }
            except Exception as e:
                logger.error(f"PNR fetch failed: {e}")
                return {
                    "success": False, 
                    "message": "Neural link timeout. Provider unreachable.",
                    "error_code": "PROVIDER_ERROR"
                }

        # Cache the result
        if result.get("success"):
            result["_cached_at"] = datetime.utcnow().timestamp()
            self._cache[pnr] = result

        # 🚀 [SECURE VAULT] Harden sensitive results if user is authenticated
        if result.get("success") and user_id and db:
            try:
                from services.vault_service import pnr_vault
                from database.models import VaultedRecord
                
                hardened = pnr_vault.pack_pnr_for_storage(user_id, pnr, result)
                
                vault_entry = VaultedRecord(
                    user_id=user_id,
                    pnr_blind_index=hardened["pnr_blind_index"],
                    encrypted_blob=hardened["encrypted_data"],
                    record_type="PNR_EXTRACTED",
                    expires_at=datetime.utcnow() + timedelta(days=2)  # Auto-scrub in 48h
                )
                db.add(vault_entry)
                db.commit()
                logger.info(f"🔒 [VAULT] Sensitive PNR {pnr[:3]}... cryptographically secured for user {user_id}")
            except Exception as ve:
                logger.error(f"Vault storage failed: {ve}")

        return result

    @retry(**RETRY_POLICY_EXTERNAL_API.__dict__)
    async def _fetch_live_status(self, pnr: str) -> Dict[str, Any]:
        """Internal method to fetch PNR status from API."""
        headers = {"x-rapidapi-key": self.api_key, "x-rapidapi-host": self.api_host}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.base_url, 
                params={"pnrNumber": pnr}, 
                headers=headers, 
                timeout=10.0
            )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("status"):
                return {
                    "success": True,
                    "pnr": pnr,
                    "status": data.get("data", {}).get("currentStatus"),
                    "train": data.get("data", {}).get("trainName"),
                    "train_number": data.get("data", {}).get("trainNo"),
                    "from_station": data.get("data", {}).get("fromStation"),
                    "to_station": data.get("data", {}).get("toStation"),
                    "journey_date": data.get("data", {}).get("journeyDate"),
                    "passengers": data.get("data", {}).get("passengers", []),
                    "message": "Live telemetry acquired."
                }
            else:
                return {
                    "success": False, 
                    "message": data.get("message", "Provider returned status False."),
                    "error_code": "PROVIDER_ERROR"
                }
        elif resp.status_code == 429:
            logger.warning(f"Rate limited for PNR {pnr}")
            return {
                "success": False, 
                "message": "Rate limit exceeded. Please try again later.",
                "error_code": "RATE_LIMIT"
            }
        else:
            return {
                "success": False, 
                "message": f"Provider error: {resp.status_code}",
                "error_code": "PROVIDER_ERROR"
            }

    def clear_cache(self, pnr: Optional[str] = None) -> None:
        """Clear PNR cache."""
        if pnr:
            self._cache.pop(pnr, None)
        else:
            self._cache.clear()
        logger.info(f"PNR cache cleared" + (f" for {pnr}" if pnr else ""))

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "ttl_seconds": self._cache_ttl_seconds
        }

    def get_health_status(self) -> Dict:
        """Get health status including circuit breaker state."""
        breaker = circuit_manager.get("pnr_service")
        metrics = breaker.get_metrics() if breaker else None
        return {
            "configured": bool(self.api_key),
            "circuit_breaker": metrics.to_dict() if metrics else None,
            "cache_stats": self.get_cache_stats()
        }


pnr_status_service = PNRStatusService()
