import logging
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
import hashlib
import time
from backend.services.cache_service import cache_service # New: Import cache_service
from backend.config import Config
from pybreaker import CircuitBreaker, CircuitBreakerError # New: Import CircuitBreaker

logger = logging.getLogger(__name__)

class RedirectService:
    """
    Service for generating and caching partner redirect URLs with affiliate links.
    Handles commission attribution and URL validation.
    """

    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for redirect URLs
        
        # Strict whitelist of allowed domains for redirects
        self.allowed_domains = {
            "www.railyatri.in",
            "www.redbus.in", 
            "www.makemytrip.com",
            "www.abhibus.com",
            "www.goibibo.com"
        }
        
        # Allowed paths for each partner (prevents path traversal)
        self.allowed_paths = {
            "RailYatri": ["/train-search", "/"],
            "RedBus": ["/bus-tickets", "/"],
            "MakeMyTrip": ["/flights", "/"],
            "AbhiBus": ["/bus-booking", "/"],
            "Goibibo": ["/flights", "/"]
        }
        
        self.partners = {
            "RailYatri": {
                "base_url": "https://www.railyatri.in",
                "commission_rate": 0.08,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster",
                "search_path": "/train-search",
                "supported_route_types": ["train"]
            },
            "RedBus": {
                "base_url": "https://www.redbus.in",
                "commission_rate": 0.06,
                "affiliate_param": "affiliateId",
                "affiliate_value": "routemaster_bus",
                "search_path": "/bus-tickets",
                "supported_route_types": ["bus"]
            },
            "MakeMyTrip": {
                "base_url": "https://www.makemytrip.com",
                "commission_rate": 0.07,
                "affiliate_param": "cmp",
                "affiliate_value": "routemaster",
                "search_path": "/flights",
                "supported_route_types": ["flight"]
            },
            "AbhiBus": {
                "base_url": "https://www.abhibus.com",
                "commission_rate": 0.05,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster_abhi",
                "search_path": "/bus-booking",
                "supported_route_types": ["bus"]
            },
            "Goibibo": {
                "base_url": "https://www.goibibo.com",
                "commission_rate": 0.06,
                "affiliate_param": "affiliate",
                "affiliate_value": "routemaster_go",
                "search_path": "/flights",
                "supported_route_types": ["flight"]
            }
        }
        
        # Circuit breaker for partner redirects to prevent cascading failures
        self.partner_breaker = CircuitBreaker(
            fail_max=Config.PARTNER_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            reset_timeout=Config.PARTNER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            exclude=Config.PARTNER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS
        )

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
        if not self._is_safe_redirect(redirect_url, partner):
            logger.error(f"Generated unsafe redirect URL: {redirect_url}")
            return None, None

        # Cache the URL
        if cache_service.is_available():
            cache_service.set(cache_key, redirect_url, ttl_seconds=self.cache_ttl)
            logger.info(f"Cached redirect URL for {cache_key}")

        return redirect_url, cache_key

    def _is_safe_redirect(self, url: str, partner: str) -> bool:
        """
        Comprehensive validation to prevent open redirect vulnerabilities.
        
        Args:
            url: The URL to validate
            partner: The partner name for path validation
            
        Returns:
            bool: True if URL is safe for redirect
        """
        try:
            parsed = urlparse(url)
            
            # 1. Must be HTTPS only (no HTTP, no protocol-relative)
            if parsed.scheme != "https":
                logger.warning(f"Redirect rejected: non-HTTPS scheme '{parsed.scheme}'")
                return False
            
            # 2. Domain must be in strict whitelist
            if parsed.netloc not in self.allowed_domains:
                logger.warning(f"Redirect rejected: domain '{parsed.netloc}' not in whitelist")
                return False
            
            # 3. Path must be in allowed paths for this partner
            if partner in self.allowed_paths:
                # Normalize path (remove trailing slash for comparison)
                path = parsed.path.rstrip('/')
                allowed_paths_normalized = [p.rstrip('/') for p in self.allowed_paths[partner]]
                if path not in allowed_paths_normalized:
                    logger.warning(f"Redirect rejected: path '{parsed.path}' not allowed for partner '{partner}'")
                    return False
            
            # 4. No fragments (#) that could be used for XSS
            if parsed.fragment:
                logger.warning(f"Redirect rejected: contains fragment '{parsed.fragment}'")
                return False
            
            # 5. Query parameter validation
            if not self._validate_query_params(parsed.query):
                return False
            
            # 6. URL length check (prevent extremely long URLs)
            if len(url) > 2048:
                logger.warning(f"Redirect rejected: URL too long ({len(url)} chars)")
                return False
            
            # 7. No null bytes or other control characters
            if '\x00' in url or any(ord(c) < 32 for c in url if c not in '\t\n\r'):
                logger.warning("Redirect rejected: contains control characters")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating redirect URL: {e}")
            return False
    
    def _validate_query_params(self, query_string: str) -> bool:
        """
        Validate query parameters for security issues.
        """
        try:
            query_params = parse_qs(query_string, keep_blank_values=True)
            
            # Dangerous patterns that could indicate XSS or other attacks
            dangerous_patterns = [
                "javascript:",
                "data:",
                "vbscript:",
                "onload=",
                "onerror=",
                "onclick=",
                "<script",
                "alert(",
                "eval(",
                "document.",
                "window.",
                "location.",
                "&#",  # HTML entities
                "%3C",  # URL encoded <
                "%3E",  # URL encoded >
            ]
            
            for param_name, param_values in query_params.items():
                # Check parameter name
                param_name_lower = param_name.lower()
                if any(dangerous in param_name_lower for dangerous in dangerous_patterns):
                    logger.warning(f"Redirect rejected: dangerous parameter name '{param_name}'")
                    return False
                
                # Check parameter values
                for value in param_values:
                    value_lower = value.lower()
                    if any(dangerous in value_lower for dangerous in dangerous_patterns):
                        logger.warning(f"Redirect rejected: dangerous parameter value in '{param_name}': '{value}'")
                        return False
                    
                    # Check for nested URL parameters that could be exploited
                    if "http" in value_lower and ("?" in value or "&" in value):
                        logger.warning(f"Redirect rejected: nested URL in parameter '{param_name}'")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating query parameters: {e}")
            return False

    def get_partner_commission_rate(self, partner: str) -> float:
        """Get the commission rate for a partner."""
        return self.partners.get(partner, {}).get("commission_rate", 0.0)

    def get_partner_health(self, partner_name: str) -> str:
        """
        Retrieves the health status of a partner from the cache.
        Returns "UNKNOWN" if not found or cache is unavailable.
        """
        if not cache_service.is_available():
            return "UNKNOWN"
        status = cache_service.get(f"partner_health:{partner_name}")
        return status if status else "UNKNOWN"

    def find_healthy_alternative_partner(
        self,
        current_partner: str,
        route_type: str,
        source: str,
        destination: str,
        avoid_partners: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Finds a healthy alternative partner for redirection if the primary partner is down.
        Considers supported route types and avoids already tried partners.
        """
        if avoid_partners is None:
            avoid_partners = []
        
        available_partners = [
            p for p in self.partners.keys()
            if p not in avoid_partners and p != current_partner # Exclude current and already avoided
        ]
        
        # Prioritize partners with higher commission rates (simple heuristic for now)
        available_partners.sort(
            key=lambda p: self.partners[p].get("commission_rate", 0.0),
            reverse=True
        )

        for p_name in available_partners:
            p_config = self.partners[p_name]
            
            # Check if partner is healthy
            health_status = self.get_partner_health(p_name)
            if health_status != "UP":
                logger.debug(f"Skipping '{p_name}' for fallback: health status is '{health_status}'")
                continue
            
            # Check if partner supports the route type
            if route_type not in p_config.get("supported_route_types", []):
                logger.debug(f"Skipping '{p_name}' for fallback: does not support route type '{route_type}'")
                continue
            
            # Add more sophisticated checks here if needed (e.g., source/destination support)
            # For now, assuming any healthy partner supporting route_type can handle source/destination
            
            logger.info(f"Found healthy alternative partner: {p_name} for route type {route_type}")
            return p_name
        
        logger.warning(f"No healthy alternative partner found for route type '{route_type}'.")
        return None

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