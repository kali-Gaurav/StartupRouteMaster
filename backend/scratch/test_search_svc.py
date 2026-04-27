
import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.search_service import SearchService
from database.session import SessionLocal

async def test_search():
    from database.session import initialize_database_pools
    await initialize_database_pools()
    svc = SearchService(db=SessionLocal())
    # Try searching NDLS to BCT (common route)
    print("Starting search...")
    try:
        # We use a date that's likely in the DB
        results = await svc.search_routes(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-01",
            budget_category="ECONOMY"
        )
        print(f"Search status: {results.get('status')}")
        if "data" in results and "journeys" in results["data"]:
            print(f"Found {len(results['data']['journeys'])} journeys")
            for j in results["data"]["journeys"][:2]:
                print(f"Journey: {j.get('journey_id')} - Score: {j.get('score')}")
        else:
            print("No journeys in results data")
            if "reasons" in results:
                print(f"Reasons: {results['reasons']}")
    except Exception as e:
        print(f"Search failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search())
