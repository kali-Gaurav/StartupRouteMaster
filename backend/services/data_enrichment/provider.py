import requests
import logging
import time
import math
from typing import Optional, Dict, Any, List
from datetime import datetime
from math import radians, cos, sin, acos
from resilience.circuit_breaker import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("data-enrichment-provider")

class EnrichmentProvider:
    """
    Interfaces with external APIs (OSM Nominatim, Overpass) 
    to fetch missing coordinates, cities, and station details.
    """
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    USER_AGENT = "RouteMaster-Enrichment-Engine/1.0"
    
    # Class-level resilience components
    _nominatim_circuit_breaker = circuit_breaker(
        name="nominatim_api",
        failure_threshold=5,
        recovery_timeout=300.0  # 5 minutes for external API
    )
    _overpass_circuit_breaker = circuit_breaker(
        name="overpass_api",
        failure_threshold=3,
        recovery_timeout=600.0  # 10 minutes for Overpass
    )
    _nominatim_retry_policy = retry_policy(
        max_attempts=3,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=1.0,
        max_delay=10.0
    )
    _overpass_retry_policy = retry_policy(
        max_attempts=2,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=2.0,
        max_delay=30.0
    )
    _metrics = MetricsClient(
        service_name="enrichment_provider",
        default_tags={"component": "data_enrichment"}
    )
    _metrics.gauge("nominatim_circuit_breaker_state", lambda: _nominatim_circuit_breaker.state.value)
    _metrics.gauge("overpass_circuit_breaker_state", lambda: _overpass_circuit_breaker.state.value)
    _metrics.counter("coordinate_lookups_total")
    _metrics.counter("coordinate_lookups_success")
    _metrics.counter("coordinate_lookups_failed")
    _metrics.counter("reverse_geocode_total")
    _metrics.counter("reverse_geocode_success")
    _metrics.counter("reverse_geocode_failed")
    _metrics.counter("facility_lookups_total")
    _metrics.counter("facility_lookups_success")
    _metrics.counter("facility_lookups_failed")
    _metrics.histogram("api_request_duration_seconds")

    @classmethod
    @track_metrics(service="enrichment_provider", operation="get_coordinates")
    @_nominatim_circuit_breaker
    @_nominatim_retry_policy
    def get_coordinates(cls, station_name: str, city: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Fetch lat/lon for a station using Nominatim."""
        query = f"{station_name} railway station"
        if city:
            query += f" {city}"
        query += " India"

        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }
        
        start_time = time.perf_counter()
        try:
            # Respect OSM usage policy (1 request per second)
            time.sleep(1.1) 
            r = requests.get(f"{cls.NOMINATIM_URL}/search", params=params, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            
            if data:
                cls._metrics.counter("coordinate_lookups_success")
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0].get("display_name")
                }
            cls._metrics.counter("coordinate_lookups_failed", tags={"reason": "no_data"})
            return None
        except Exception as e:
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            cls._metrics.counter("coordinate_lookups_failed", tags={"error_type": type(e).__name__})
            logger.error(f"Nominatim lookup failed for {query}: {e}")
            raise

    @classmethod
    @track_metrics(service="enrichment_provider", operation="reverse_geocode")
    @_nominatim_circuit_breaker
    @_nominatim_retry_policy
    def reverse_geocode(cls, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch city/address details from coordinates."""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json"
        }
        
        start_time = time.perf_counter()
        try:
            time.sleep(1.1)
            r = requests.get(f"{cls.NOMINATIM_URL}/reverse", params=params, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            
            if data and "address" in data:
                address = data["address"]
                # Try to find city in different possible OSM tags
                city = address.get("city") or address.get("town") or address.get("village") or address.get("district")
                state = address.get("state")
                cls._metrics.counter("reverse_geocode_success")
                return {
                    "city": city,
                    "state": state,
                    "full_address": data.get("display_name")
                }
            cls._metrics.counter("reverse_geocode_failed", tags={"reason": "no_data"})
            return None
        except Exception as e:
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            cls._metrics.counter("reverse_geocode_failed", tags={"error_type": type(e).__name__})
            logger.error(f"Reverse geocoding failed for {lat},{lon}: {e}")
            raise

    @classmethod
    def haversine_distance(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        if not all([lat1, lon1, lat2, lon2]): return 0.0
        try:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            # Law of cosines for better performance than full Haversine on modern CPUs
            dist = 6371 * acos(
                min(1.0, cos(lat1) * cos(lat2) * cos(lon2 - lon1) + sin(lat1) * sin(lat2))
            )
            return round(dist, 2)
        except Exception:
            return 0.0

    @classmethod
    @track_metrics(service="enrichment_provider", operation="get_station_facilities")
    @_overpass_circuit_breaker
    @_overpass_retry_policy
    def get_station_facilities(cls, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch station facilities using Overpass API."""
        # Search in 500m radius
        query = f"""
        [out:json];
        node["railway"="station"](around:500,{lat},{lon});
        out body;
        """
        start_time = time.perf_counter()
        try:
            r = requests.post(cls.OVERPASS_URL, data={"data": query}, headers={"User-Agent": cls.USER_AGENT})
            r.raise_for_status()
            data = r.json()
            
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            
            if data and "elements" in data and len(data["elements"]) > 0:
                tags = data["elements"][0].get("tags", {})
                cls._metrics.counter("facility_lookups_success")
                return {
                    "wheelchair": tags.get("wheelchair"),
                    "platforms": tags.get("platforms"),
                    "operator": tags.get("operator"),
                    "amenities": [k for k in tags.keys() if k.startswith("amenity")]
                }
            cls._metrics.counter("facility_lookups_failed", tags={"reason": "no_data"})
            return {}
        except Exception as e:
            duration = time.perf_counter() - start_time
            cls._metrics.histogram("api_request_duration_seconds", duration)
            cls._metrics.counter("facility_lookups_failed", tags={"error_type": type(e).__name__})
            logger.error(f"Overpass facility fetch failed: {e}")
            raise

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "enrichment_provider",
            "nominatim_circuit_breaker_state": cls._nominatim_circuit_breaker.state.name,
            "nominatim_circuit_breaker_failures": cls._nominatim_circuit_breaker.failure_count,
            "overpass_circuit_breaker_state": cls._overpass_circuit_breaker.state.name,
            "overpass_circuit_breaker_failures": cls._overpass_circuit_breaker.failure_count,
            "coordinate_lookups_total": cls._metrics.get_counter("coordinate_lookups_total"),
            "coordinate_lookups_success": cls._metrics.get_counter("coordinate_lookups_success"),
            "coordinate_lookups_failed": cls._metrics.get_counter("coordinate_lookups_failed"),
            "reverse_geocode_total": cls._metrics.get_counter("reverse_geocode_total"),
            "reverse_geocode_success": cls._metrics.get_counter("reverse_geocode_success"),
            "reverse_geocode_failed": cls._metrics.get_counter("reverse_geocode_failed"),
            "facility_lookups_total": cls._metrics.get_counter("facility_lookups_total"),
            "facility_lookups_success": cls._metrics.get_counter("facility_lookups_success"),
            "facility_lookups_failed": cls._metrics.get_counter("facility_lookups_failed"),
            "api_request_duration_p50": cls._metrics.get_percentile("api_request_duration_seconds", 50),
            "api_request_duration_p95": cls._metrics.get_percentile("api_request_duration_seconds", 95),
        }

    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if (cls._nominatim_circuit_breaker.state == CircuitState.CLOSED and 
                                   cls._overpass_circuit_breaker.state == CircuitState.CLOSED) else "degraded",
            "service": "enrichment_provider",
            "nominatim_circuit_breaker": cls._nominatim_circuit_breaker.state.name,
            "overpass_circuit_breaker": cls._overpass_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    @classmethod
    def reset_circuit_breaker(cls, breaker_name: str = "all"):
        """Reset circuit breaker(s) to closed state."""
        if breaker_name == "all" or breaker_name == "nominatim":
            cls._nominatim_circuit_breaker.reset()
        if breaker_name == "all" or breaker_name == "overpass":
            cls._overpass_circuit_breaker.reset()
        logger.info(f"🔄 [ENRICHMENT] Circuit breaker '{breaker_name}' reset")