
import asyncio
import os
import sys
import json
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.search_service import SearchService
from database.session import SessionLocal, initialize_database_pools

async def test_search():
    await initialize_database_pools()
    db = SessionLocal()
    svc = SearchService(db=db)
    
    print("--- STARTING SEARCH ---")
    try:
        results = await svc.search_routes(
            source="NDLS",
            destination="BCT",
            travel_date="2026-05-01"
        )
        print("--- SEARCH RESULTS ---")
        # Print only keys and journey count for brevity, but full JSON if small
        print(json.dumps(results, indent=2, default=str))
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_search())
