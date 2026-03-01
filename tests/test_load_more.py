import asyncio
import time
from datetime import datetime, timedelta
import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from services.search_service import SearchService
from database.session import SessionLocal

async def test_load_more_kota_to_palakkad():
    db = SessionLocal()
    search_svc = SearchService(db)
    
    source = "KOTA"
    dest = "PGT"
    date_str = "2026-03-02"
    
    print(f"\n--- Testing Initial Search: {source} to {dest} (Page 1) ---")
    start = time.time()
    # Initial request: first 5 routes
    result1 = await search_svc.search_routes(source, dest, date_str, offset=0, limit=5)
    duration1 = (time.time() - start) * 1000
    
    print(f"Results Found: {len(result1.get('journeys', []))}")
    print(f"Total Available: {result1.get('total_available')}")
    print(f"Latency: {duration1:.2f}ms")
    
    for i, j in enumerate(result1.get('journeys', [])):
        print(f"  [{i+1}] {j['journey_id']} - Duration: {j['total_duration']}m")

    print(f"\n--- Testing 'Load More': {source} to {dest} (Page 2) ---")

    start = time.time()
    # Second request: next 5 routes (should be a CACHE HIT)
    result2 = await search_svc.search_routes(source, dest, date_str, offset=5, limit=5)
    duration2 = (time.time() - start) * 1000
    
    print(f"Results Found: {len(result2.get('journeys', []))}")
    print(f"Total Available: {result2.get('total_available')}")
    print(f"Latency (Expected fast cache hit): {duration2:.2f}ms")
    
    for i, j in enumerate(result2.get('journeys', [])):
        print(f"  [{i+6}] {j['journey_id']} - Duration: {j['total_duration']}m")

    db.close()

if __name__ == "__main__":
    asyncio.run(test_load_more_kota_to_palakkad())
