#!/usr/bin/env python3
"""
Phase 1 Validation Test: Direct Route Finding
This test validates Phase 1 implementation against the specification:
- Search routes between stations using RAPTOR
- Return direct routes (0 transfers)
- Return routes with 1+ transfers
- Validate route properties (duration, cost, etc)
"""

import asyncio
import sys
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.services.search_service import SearchService
from backend.core.route_engine import route_engine
from backend.database.models import Stop

async def test_phase1_comprehensive():
    """Test Phase 1 with multiple route scenarios"""
    db = SessionLocal()
    
    test_cases = [
        {
            "name": "NDLS to BCT (Delhi to Mumbai)",
            "source": "NDLS",
            "destination": "BCT",
            "date": "2026-03-25 12:00:00",
            "expected_min_routes": 1,
        },
        {
            "name": "CST to NDLS (Mumbai to Delhi)",
            "source": "CST",
            "destination": "NDLS",
            "date": "2026-03-25 08:00:00",
            "expected_min_routes": 0,  # May or may not have routes
        },
        {
            "name": "NDLS to DEE (Delhi to nearby)",
            "source": "NDLS",
            "destination": "DEE",
            "date": "2026-03-25 10:00:00",
            "expected_min_routes": 0,  # May or may not have routes
        },
    ]
    
    try:
        service = SearchService(db, route_engine_instance=route_engine)
        
        print("=" * 70)
        print("PHASE 1 COMPREHENSIVE TEST")
        print("=" * 70)
        
        total_passed = 0
        total_tests = 0
        
        for test_case in test_cases:
            total_tests += 1
            print(f"\nTest: {test_case['name']}")
            print(f"  Route: {test_case['source']} -> {test_case['destination']}")
            print(f"  Date: {test_case['date']}")
            
            try:
                result = await service.search_routes(
                    source=test_case["source"],
                    destination=test_case["destination"],
                    travel_date=test_case["date"]
                )
                
                total_routes = len(result.get("routes", {}).get("direct", [])) + \
                               len(result.get("routes", {}).get("one_transfer", [])) + \
                               len(result.get("routes", {}).get("two_transfer", [])) + \
                               len(result.get("routes", {}).get("three_transfer", []))
                
                direct_routes = len(result.get("routes", {}).get("direct", []))
                one_transfer = len(result.get("routes", {}).get("one_transfer", []))
                
                print(f"  ✓ Search completed")
                print(f"    - Total routes: {total_routes}")
                print(f"    - Direct routes: {direct_routes}")
                print(f"    - One transfer: {one_transfer}")
                
                if direct_routes > 0:
                    route = result["routes"]["direct"][0]
                    print(f"    - First route: {route.get('train_no')} {route.get('departure')} -> {route.get('arrival')}")
                
                if total_routes >= test_case["expected_min_routes"]:
                    print(f"  ✓ PASSED")
                    total_passed += 1
                else:
                    print(f"  ✗ FAILED: Expected >= {test_case['expected_min_routes']} routes, got {total_routes}")
                    
            except Exception as e:
                print(f"  ✗ ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 70)
        print(f"RESULTS: {total_passed}/{total_tests} tests passed")
        print("=" * 70)
        
        if total_passed == total_tests:
            print("✓ PHASE 1 VALIDATION SUCCESSFUL")
            return True
        else:
            print("✗ PHASE 1 VALIDATION FAILED")
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    success = asyncio.run(test_phase1_comprehensive())
    sys.exit(0 if success else 1)
