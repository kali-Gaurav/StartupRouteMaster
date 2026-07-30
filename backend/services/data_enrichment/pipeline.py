import logging
import json
import time
from datetime import datetime
from typing import Any, cast, List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from .provider import EnrichmentProvider
from database.models import Stop, Segment
from database.session import SessionTransit
from resilience import circuit_breaker, CircuitState
from resilience.retry_policy import retry_policy, RetryStrategy
from resilience.metrics import track_metrics, MetricsClient

logger = logging.getLogger("data-enrichment-pipeline")

class DataEnrichmentPipeline:
    """
    Subtask 50.1: Automatic Data Enrichment Pipeline.
    Orchestrates scanning, fetching, and updating transit data.
    """
    
    # Circuit breaker for pipeline operations
    _pipeline_circuit_breaker = circuit_breaker(
        name="data_enrichment_pipeline",
        failure_threshold=3,
        recovery_timeout=1800.0  # 30 minutes
    )
    # Retry policy for DB operations
    _db_retry_policy = retry_policy(
        max_attempts=3,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay=0.5,
        max_delay=10.0
    )
    # Metrics tracking
    _metrics = MetricsClient(
        service_name="data_enrichment_pipeline",
        default_tags={"component": "data_enrichment"}
    )
    _metrics.gauge("circuit_breaker_state", lambda: _pipeline_circuit_breaker.state.value)
    _metrics.counter("enrichment_cycles_total")
    _metrics.counter("enrichment_cycles_success")
    _metrics.counter("enrichment_cycles_failed")
    _metrics.counter("stations_enriched_total")
    _metrics.counter("segments_enriched_total")
    _metrics.histogram("enrichment_cycle_duration_seconds")
    
    @classmethod
    @track_metrics(service="data_enrichment_pipeline", operation="run_full_enrichment")
    @_pipeline_circuit_breaker
    @_db_retry_policy
    async def run_full_enrichment(cls, batch_limit: int = 100):
        """Run a full pass of data enrichment."""
        db = SessionTransit()
        try:
            # 1. Fix Stations (Coordinates & Cities)
            await cls.enrich_stations(db, batch_limit)
            
            # 2. Fix Segments (Distances)
            await cls.enrich_segments(db, batch_limit * 5)
            
            db.commit()
            logger.info("✅ Data Enrichment Cycle Complete.")
        finally:
            db.close()

    @classmethod
    async def enrich_stations(cls, db: Session, limit: int):
        """Find stations with low quality scores or missing data and repair them."""
        # Find 0.0 coordinates or those with score < 50
        stations = db.query(Stop).filter(
            (Stop.latitude == 0.0) | (Stop.longitude == 0.0) | (Stop.data_quality_score < 50)
        ).limit(limit).all()
        
        logger.info(f"Scanning {len(stations)} stations for enrichment...")
        
        for stop in stations:
            stop_obj = cast(Any, stop)
            initial_score = int(stop_obj.data_quality_score or 0)
            latitude = float(stop_obj.latitude or 0.0)
            longitude = float(stop_obj.longitude or 0.0)
            city = str(stop_obj.city) if stop_obj.city else ""
            new_score = 0

            # A. Fix Coordinates if missing
            if latitude == 0.0 or longitude == 0.0:
                coords = EnrichmentProvider.get_coordinates(stop_obj.name, city or None)
                if coords:
                    latitude = float(coords["lat"])
                    longitude = float(coords["lon"])
                    stop_obj.latitude = latitude
                    stop_obj.longitude = longitude
                    logger.info(f"Fixed coordinates for {stop_obj.code}: {latitude}, {longitude}")

            if latitude != 0.0 and longitude != 0.0:
                new_score += 30

                # B. Verify/Fix City via Reverse Geocoding
                # Only re-verify if score is low or city seems suspicious
                if not city or initial_score < 20:
                    geo_info = EnrichmentProvider.reverse_geocode(latitude, longitude)
                    if geo_info and geo_info.get("city"):
                        if city != geo_info["city"]:
                            logger.warning(f"City Correction: {stop_obj.code} '{city}' -> '{geo_info['city']}'")
                            stop_obj.city = geo_info["city"]
                        stop_obj.state = geo_info.get("state") or stop_obj.state
                        new_score += 20
                else:
                    new_score += 20 # Already has verified city

            # C. Facilities Enrichment
            if initial_score < 60:
                facilities = EnrichmentProvider.get_station_facilities(latitude, longitude)
                if facilities:
                    from database.models import StationFacilities
                    if not stop_obj.facilities:
                        stop_obj.facilities = StationFacilities(stop_id=stop_obj.id)
                    new_score += 10

            stop_obj.data_quality_score = new_score
            logger.info(f"Station {stop_obj.code} quality score: {initial_score} -> {new_score}")

    @classmethod
    async def enrich_segments(cls, db: Session, limit: int):
        """Compute distances for segments where it is 0.0."""
        # Use a join to get coordinates of both stops efficiently
        segments = db.query(Segment).filter(
            (Segment.distance_km == 0.0) | (Segment.distance_km == None)
        ).limit(limit).all()
        
        logger.info(f"Computing distances for {len(segments)} segments...")
        
        # Pre-fetch stop coordinates to avoid N+1
        stop_ids = set()
        for seg in segments:
            stop_ids.add(seg.source_stop_id)
            stop_ids.add(seg.destination_stop_id)
            
        stops = {s.id: s for s in db.query(Stop).filter(Stop.id.in_(list(stop_ids))).all()}
        
        count = 0
        for seg in segments:
            s1 = stops.get(seg.source_stop_id)
            s2 = stops.get(seg.destination_stop_id)
            if not s1 or not s2:
                continue

            s1_obj = cast(Any, s1)
            s2_obj = cast(Any, s2)
            lat1 = float(s1_obj.latitude or 0.0)
            lon1 = float(s1_obj.longitude or 0.0)
            lat2 = float(s2_obj.latitude or 0.0)
            lon2 = float(s2_obj.longitude or 0.0)

            if lat1 == 0.0 or lon1 == 0.0 or lat2 == 0.0 or lon2 == 0.0:
                continue

            dist = EnrichmentProvider.haversine_distance(lat1, lon1, lat2, lon2)
            if dist > 0:
                seg_obj = cast(Any, seg)
                seg_obj.distance_km = round(dist * 1.2, 2)
                seg_obj.data_quality_score = 100
                count += 1
        
        logger.info(f"Successfully enriched {count} segments with distance data.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(DataEnrichmentPipeline.run_full_enrichment())

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "service": "data_enrichment_pipeline",
            "circuit_breaker_state": cls._pipeline_circuit_breaker.state.name,
            "circuit_breaker_failures": cls._pipeline_circuit_breaker.failure_count,
            "enrichment_cycles_total": cls._metrics.get_counter("enrichment_cycles_total"),
            "enrichment_cycles_success": cls._metrics.get_counter("enrichment_cycles_success"),
            "enrichment_cycles_failed": cls._metrics.get_counter("enrichment_cycles_failed"),
            "stations_enriched_total": cls._metrics.get_counter("stations_enriched_total"),
            "segments_enriched_total": cls._metrics.get_counter("segments_enriched_total"),
            "enrichment_cycle_duration_p50": cls._metrics.get_percentile("enrichment_cycle_duration_seconds", 50),
            "enrichment_cycle_duration_p95": cls._metrics.get_percentile("enrichment_cycle_duration_seconds", 95),
        }

    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """Health check endpoint data."""
        return {
            "status": "healthy" if cls._pipeline_circuit_breaker.state == CircuitState.CLOSED else "degraded",
            "service": "data_enrichment_pipeline",
            "circuit_breaker": cls._pipeline_circuit_breaker.state.name,
            "timestamp": datetime.utcnow().isoformat()
        }

    @classmethod
    def reset_circuit_breaker(cls):
        """Reset the circuit breaker to closed state."""
        cls._pipeline_circuit_breaker.reset()
        logger.info("🔄 [ENRICHMENT] Circuit breaker reset for data enrichment pipeline")
