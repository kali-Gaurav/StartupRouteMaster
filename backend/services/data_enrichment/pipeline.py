import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from .provider import EnrichmentProvider
from database.models import Stop, Segment
from database.session import SessionTransit

logger = logging.getLogger("data-enrichment-pipeline")

class DataEnrichmentPipeline:
    """
    Subtask 50.1: Automatic Data Enrichment Pipeline.
    Orchestrates scanning, fetching, and updating transit data.
    """
    
    @classmethod
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
            initial_score = stop.data_quality_score or 0
            new_score = 0
            
            # A. Fix Coordinates if missing
            if stop.latitude == 0.0 or stop.longitude == 0.0:
                coords = EnrichmentProvider.get_coordinates(stop.name, stop.city)
                if coords:
                    stop.latitude = coords["lat"]
                    stop.longitude = coords["lon"]
                    logger.info(f"Fixed coordinates for {stop.code}: {stop.latitude}, {stop.longitude}")
            
            if stop.latitude != 0.0 and stop.longitude != 0.0:
                new_score += 30
                
                # B. Verify/Fix City via Reverse Geocoding
                # Only re-verify if score is low or city seems suspicious
                if not stop.city or stop.data_quality_score < 20:
                    geo_info = EnrichmentProvider.reverse_geocode(stop.latitude, stop.longitude)
                    if geo_info and geo_info.get("city"):
                        # [BUGFIX] If the new city is different, update it
                        if stop.city != geo_info["city"]:
                            logger.warning(f"City Correction: {stop.code} '{stop.city}' -> '{geo_info['city']}'")
                            stop.city = geo_info["city"]
                        stop.state = geo_info.get("state") or stop.state
                        new_score += 20
                else:
                    new_score += 20 # Already has verified city
            
            # C. Facilities Enrichment
            if stop.data_quality_score < 60:
                facilities = EnrichmentProvider.get_station_facilities(stop.latitude, stop.longitude)
                if facilities:
                    from database.models import StationFacilities
                    if not stop.facilities:
                        stop.facilities = StationFacilities(stop_id=stop.id)
                    # Implementation details for facility storage...
                    new_score += 10
            
            stop.data_quality_score = new_score
            logger.info(f"Station {stop.code} quality score: {initial_score} -> {new_score}")

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
            
            if s1 and s2 and s1.latitude != 0.0 and s2.latitude != 0.0:
                dist = EnrichmentProvider.haversine_distance(
                    s1.latitude, s1.longitude, s2.latitude, s2.longitude
                )
                if dist > 0:
                    # Rail distance is typically ~1.2x straight line (Haversine)
                    seg.distance_km = round(dist * 1.2, 2)
                    seg.data_quality_score = 100
                    count += 1
        
        logger.info(f"Successfully enriched {count} segments with distance data.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(DataEnrichmentPipeline.run_full_enrichment())
