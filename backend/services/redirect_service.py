import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
import hashlib
import time
from backend.services.cache_service import cache_service
from backend.config import Config

logger = logging.getLogger(__name__)

class RedirectService:
    """
    Service for generating and caching partner redirect URLs with affiliate links.
    Handles commission attribution and URL validation.
    """

    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for redirect URLs
        self.partners = {
            "RailYatri": {
                "base_url": "https://www.railyatri.in",
                "commission_rate": 0.08,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster",
                "search_path": "/train-search"
            },
            "RedBus": {
                "base_url": "https://www.redbus.in",
                "commission_rate": 0.06,
                "affiliate_param": "affiliateId",
                "affiliate_value": "routemaster_bus",
                "search_path": "/bus-tickets"
            },
            "MakeMyTrip": {
                "base_url": "https://www.makemytrip.com",
                "commission_rate": 0.07,
                "affiliate_param": "cmp",
                "affiliate_value": "routemaster",
                "search_path": "/flights"
            },
            "AbhiBus": {
                "base_url": "https://www.abhibus.com",
                "commission_rate": 0.05,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster_abhi",
                "search_path": "/bus-booking"
            },
            "Goibibo": {
                "base_url": "https://www.goibibo.com",
                "commission_rate": 0.06,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster_go",
                "search_path": "/flights"
            }
        }

    def generate_redirect_url(
        self,
        partner: str,
        route_type: str,
        source: str,
        destination: str,
        date: str,
        passengers: int = 1
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate a cached redirect URL for a partner booking site.

        Returns: (redirect_url, cache_key)
        """
        if partner not in self.partners:
            logger.error(f"Unknown partner: {partner}")
            return None, None

        partner_config = self.partners[partner]

        # Create cache key for this redirect
        cache_key_data = f"{partner}:{route_type}:{source}:{destination}:{date}:{passengers}"
        cache_key = f"redirect:{hashlib.md5(cache_key_data.encode()).hexdigest()}"

        # Check cache first
        if cache_service.is_available():
            cached_url = cache_service.get(cache_key)
            if cached_url:
                logger.info(f"Redirect URL cache hit for {cache_key}")
                return cached_url, cache_key

        # Generate URL based on route type
        base_url = partner_config["base_url"]
        search_path = partner_config["search_path"]

        # Build query parameters
        params = {
            partner_config["affiliate_param"]: partner_config["affiliate_value"],
        }

        if route_type == "train":
            params.update({
                "from": source,
                "to": destination,
                "date": date,
                "class": "SL",  # Default to sleeper class
                "quota": "GN"   # General quota
            })
        elif route_type == "bus":
            params.update({
                "from": source,
                "to": destination,
                "date": date,
                "passengers": str(passengers)
            })
        elif route_type == "flight":
            params.update({
                "from": source,
                "to": destination,
                "date": date,
                "adults": str(passengers),
                "class": "economy"
            })

        # Build final URL
        query_string = urlencode(params)
        redirect_url = f"{base_url}{search_path}?{query_string}"

        # Validate URL is safe (only allow known domains)
        if not self._is_safe_redirect(redirect_url, partner_config["base_url"]):
            logger.error(f"Generated unsafe redirect URL: {redirect_url}")
            return None, None

        # Cache the URL
        if cache_service.is_available():
            cache_service.set(cache_key, redirect_url, ttl=self.cache_ttl)
            logger.info(f"Cached redirect URL for {cache_key}")

        return redirect_url, cache_key

    def _is_safe_redirect(self, url: str, expected_domain: str) -> bool:
        """
        Validate that the redirect URL is safe and points to the expected domain.
        """
        try:
            parsed = urlparse(url)
            expected_parsed = urlparse(expected_domain)

            # Must be HTTPS
            if parsed.scheme != "https":
                return False

            # Must match expected domain
            if parsed.netloc != expected_parsed.netloc:
                return False

            # No suspicious query parameters
            suspicious_params = ["javascript", "data", "vbscript"]
            query_params = parse_qs(parsed.query)
            for param_values in query_params.values():
                for value in param_values:
                    if any(suspicious in value.lower() for suspicious in suspicious_params):
                        return False

            return True
        except Exception as e:
            logger.error(f"Error validating redirect URL: {e}")
            return False

    def get_partner_commission_rate(self, partner: str) -> float:
        """Get the commission rate for a partner."""
        return self.partners.get(partner, {}).get("commission_rate", 0.0)

    def invalidate_redirect_cache(self, pattern: str = "*"):
        """Invalidate cached redirect URLs matching a pattern."""
        if cache_service.is_available():
            # This would require a more advanced cache operation
            # For now, we'll let cache entries expire naturally
            logger.info(f"Redirect cache invalidation requested for pattern: {pattern}")
            return True
        return False

# Global instance
redirect_service = RedirectService()