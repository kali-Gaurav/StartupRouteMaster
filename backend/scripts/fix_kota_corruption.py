import sys
import os
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_enrichment.provider import EnrichmentProvider
from database.session import SessionTransit
from database.models import Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix-kota-corruption")

async def fix_kota():
    db = SessionTransit()
    try:
        # Find all stops mislabeled as Kota (except actual Kota)
        # We also check for 'KOTA' which is standard in some raw imports
        stops = db.query(Stop).filter(Stop.city == 'Kota', Stop.code != 'KOTA').all()
        logger.info(f"Found {len(stops)} suspicious 'Kota' stations. Repairing...")
        
        for stop in stops:
            if stop.latitude == 0 or stop.longitude == 0:
                logger.warning(f"Skipping {stop.code} - no coordinates.")
                # Fallback to station name if no coords
                stop.city = stop.name
                continue
                
            geo = EnrichmentProvider.reverse_geocode(stop.latitude, stop.longitude)
            if geo and geo.get("city"):
                new_city = geo["city"]
                if new_city.lower() != 'kota':
                    logger.info(f"Fixed {stop.code}: {stop.name} is in {new_city}")
                    stop.city = new_city
                    stop.data_quality_score = (stop.data_quality_score or 0) + 20
            else:
                logger.warning(f"Reverse geocode failed for {stop.code}. Unsetting city.")
                stop.city = stop.name
        
        db.commit()
        logger.info("Database correction committed.")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(fix_kota())
