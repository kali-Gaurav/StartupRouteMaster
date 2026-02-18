#!/usr/bin/env python3
"""Test and analyze the route generation system."""

import requests
import json
import sys

def test_route_system():
    """Test the route generation system."""
    
    print("=" * 70)
    print("ROUTEMASTER ROUTE GENERATION SYSTEM TEST")
    print("=" * 70)
    
    # Test 1: Backend connectivity
    print("\n[TEST 1] Backend Connectivity")
    print("-" * 70)
    try:
        r = requests.get('http://localhost:8000/', timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"✓ Backend responding")
            print(f"  Title: {data.get('title')}")
            print(f"  Version: {data.get('version')}")
        else:
            print(f"✗ Backend error: {r.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to backend: {e}")
        return False
    
    # Test 2: Check registered endpoints
    print("\n[TEST 2] Registered Endpoints")
    print("-" * 70)
    try:
        r = requests.get('http://localhost:8000/openapi.json', timeout=5)
        if r.status_code == 200:
            paths = sorted(r.json().get('paths', {}).keys())
            print(f"✓ Total endpoints: {len(paths)}")
            
            search_paths = [p for p in paths if 'search' in p.lower()]
            print(f"  Search endpoints: {len(search_paths)}")
            for p in search_paths[:5]:
                print(f"    - {p}")
            
            journey_paths = [p for p in paths if 'journey' in p.lower()]
            print(f"  Journey endpoints: {len(journey_paths)}")
            for p in journey_paths[:3]:
                print(f"    - {p}")
    except Exception as e:
        print(f"✗ Error getting endpoints: {e}")
    
    # Test 3: Popular routes
    print("\n[TEST 3] Route Data Availability")
    print("-" * 70)
    try:
        r = requests.get('http://localhost:8000/api/popular-routes', timeout=5)
        if r.status_code == 200:
            routes = r.json()
            print(f"✓ Popular routes endpoint working")
            print(f"  Routes available: {len(routes)}")
            if routes:
                print(f"  Route structure: {list(routes[0].keys())[:5]}")
        else:
            print(f"  Popular routes: {r.status_code}")
    except Exception as e:
        print(f"  Popular routes error: {e}")
    
    # Test 4: Stations
    print("\n[TEST 4] Station Data")
    print("-" * 70)
    try:
        r = requests.get('http://localhost:8000/stations/search?q=delhi', timeout=5)
        if r.status_code == 200:
            stations = r.json()
            print(f"✓ Station search working")
            print(f"  Stations found for 'delhi': {len(stations) if isinstance(stations, list) else 'N/A'}")
            if isinstance(stations, list) and stations:
                print(f"  Sample station: {stations[0]}")
        else:
            print(f"  Station search: {r.status_code}")
    except Exception as e:
        print(f"  Station search error: {e}")
    
    # Test 5: Try basic routes endpoint
    print("\n[TEST 5] Basic Route Search")
    print("-" * 70)
    try:
        r = requests.get('http://localhost:8000/routes', 
                        params={'source': 'NDLS', 'destination': 'CSMT'},
                        timeout=5)
        if r.status_code == 200:
            result = r.json()
            print(f"✓ Routes endpoint working")
            print(f"  Response type: {type(result).__name__}")
            if isinstance(result, dict):
                print(f"  Response keys: {list(result.keys())[:5]}")
            elif isinstance(result, list):
                print(f"  Routes count: {len(result)}")
        else:
            print(f"  Routes endpoint: {r.status_code}")
    except Exception as e:
        print(f"  Routes error: {e}")
    
    print("\n" + "=" * 70)
    print("ROUTE GENERATION ENGINE FILES")
    print("=" * 70)
    print("""
    Key files for route generation:
    
    1. backend/services/route_engine.py
       - Class: RouteEngine
       - Purpose: Core route optimization using RAPTOR algorithm
       - Key methods:
         * load_graph_from_db(db) - Load graph from database
         * find_routes(source, dest, date, ...) - Main search
         * score_and_rank(routes) - Rank routes
    
    2. backend/services/multi_modal_route_engine.py
       - Class: MultiModalRouteEngine
       - Purpose: GTFS-based multi-modal routing (trains, buses, metro)
       - Key methods:
         * search_single_journey(source_id, dest_id, date)
         * search_connecting_journeys(...)
         * search_round_trip(...)
    
    3. backend/api/search.py
       - Endpoint: POST /api/search
       - Purpose: Entry point for route search from frontend
       - Uses: multi_modal_route_engine
    
    4. backend/api/integrated_search.py
       - Endpoints: /api/v2/search/unified
       - Purpose: Unified search with journey reconstruction
       - Status: May have configuration issues
    
    5. backend/services/journey_reconstruction.py
       - Purpose: Construct complete journey information
       - Used by: integrated_search API
    """)
    
    print("\n" + "=" * 70)
    print("NEXT STEPS FOR FULL ROUTE GENERATION")
    print("=" * 70)
    print("""
    1. Verify database has train/transit data loaded
    2. Test multi_modal_route_engine.search_single_journey() directly
    3. Check journey_reconstruction engine integration
    4. Implement frontend API call to /api/search or /api/v2/search/unified
    5. Add route filtering/ranking based on user preferences
    """)

if __name__ == "__main__":
    test_route_system()
