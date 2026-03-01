#!/usr/bin/env python3
"""Quick Phase 1 test"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.services.search_service import SearchService
from backend.core.route_engine import route_engine
import logging

logging.getLogger("backend").setLevel(logging.WARNING)

async def test():
    db = SessionLocal()
    service = SearchService(db, route_engine_instance=route_engine)
    
    result = await service.search_routes(
        source="NDLS",
        destination="BCT",
        travel_date="2026-03-25 12:00:00"
    )
    
    print("[PASS] PHASE 1 TEST PASSED")
    print(f"  Routes Found: {len(result.get('routes', {}).get('direct', []))}")
    print(f"  Message: {result.get('journey_message')}")
    
    if result.get('routes', {}).get('direct'):
        rt = result['routes']['direct'][0]
        print(f"  Route: {rt['train_no']} {rt['departure']} -> {rt['arrival']} ({rt['time_str']})")
    
    db.close()

asyncio.run(test())
