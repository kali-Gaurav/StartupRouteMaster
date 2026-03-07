import asyncio
from datetime import datetime
import logging
from database.session import SessionLocal
from services.search_service import SearchService

logging.basicConfig(level=logging.INFO)

async def verify_deduplication():
    db = SessionLocal()
    service = SearchService(db)
    
    source = "PGT"
    destination = "KOTA"
    date_str = "2026-03-08"
    
    print(f"\n>>> Running Strict Deduplication Test: {source} -> {destination}")
    
    res = await service.search_routes(source, destination, date_str)
    
    journeys = res.get("journeys", [])
    journey_ids = [j.get("journey_id") for j in journeys]
    
    unique_ids = set(journey_ids)
    
    print(f"Total Journeys Returned: {len(journey_ids)}")
    print(f"Unique Journey IDs: {len(unique_ids)}")
    
    if len(journey_ids) != len(unique_ids):
        print("❌ FAILURE: Duplicates detected in search response!")
        # Find which ones are duplicates
        seen = set()
        dupes = []
        for jid in journey_ids:
            if jid in seen:
                dupes.append(jid)
            seen.add(jid)
        print(f"Duplicate IDs: {set(dupes)}")
        return False
    else:
        print("✅ SUCCESS: Zero duplicates found. Deduplication is solid.")
        return True

if __name__ == "__main__":
    import os
    import sys
    # Add backend to path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    asyncio.run(verify_deduplication())
