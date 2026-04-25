
import asyncio
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from database.session import initialize_database_pools, SessionUser, SessionTransit
from services.search_service import SearchService
from core.nexus.bootstrapper import nexus_boot

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("test_search_e2e")

async def test_search():
    print("\nStarting E2E Search Test...")
    
    # 1. Boot Nexus
    print("Layer 1: Booting Nexus Fiber...")
    await nexus_boot.bootstrap()
    
    # Enable JIT pools if not already done by nexus
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    try:
        # 2. Initialize Search Service
        # We need a User DB session for search logging
        with SessionUser() as db:
            search_service = SearchService(db)
            
            # 3. Perform Search
            source = "NDLS"
            destination = "HWH"
            travel_date = "2026-05-20" # Use a future date in 2026
            
            print(f"Layer 2: Searching for {source} -> {destination} on {travel_date}...")
            start_time = datetime.now()
            
            results = await search_service.search_routes(
                source=source,
                destination=destination,
                travel_date=travel_date,
                budget_category="COMFORT",
                quota="GN"
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            print(f"Search complete in {duration:.2f}s")
            
            # 4. Analyze Results
            print("\nAnalysis Summary:")
            print(f"Status: {results.get('status')}")
            print(f"Found {results.get('total_available', 0)} total candidates.")
            
            journeys = results.get('data', {}).get('journeys', [])
            print(f"Top {len(journeys)} masked journeys returned.")
            
            if journeys:
                first = journeys[0]
                print(f"Sample Journey ID: {first.get('journey_id')}")
                print(f"Masked Segments: {len(first.get('segments', []))}")
                print(f"UI Reasons: {first.get('metadata', {}).get('ui_reasons', [])}")
            
            # 5. Check Ingestion Worker (it should be running in background)
            from services.realtime_ingestion.ingestion_worker import get_ingestion_worker
            worker = get_ingestion_worker()
            if worker:
                print(f"Ingestion Worker: ONLINE (Stats: {worker.get_stats()})")
            else:
                print("Ingestion Worker: OFFLINE")

    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nLayer 3: Shutting down...")
        await nexus_boot.halt()

if __name__ == "__main__":
    asyncio.run(test_search())
