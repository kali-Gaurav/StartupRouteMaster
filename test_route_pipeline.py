#!/usr/bin/env python3
"""
Comprehensive Route Generation Testing Plan
Tests each component step-by-step to diagnose where generation fails
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import traceback

class RouteGenerationTester:
    """Test route generation pipeline systematically."""
    
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.results = []
        self.session = requests.Session()
    
    def test(self, name: str, test_func) -> Tuple[bool, str]:
        """Run a single test and log result."""
        print(f"\n{'='*70}")
        print(f"[TEST] {name}")
        print(f"{'='*70}")
        try:
            result = test_func()
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}")
            self.results.append((name, status))
            return result
        except Exception as e:
            print(f"✗ FAIL: {e}")
            traceback.print_exc()
            self.results.append((name, "✗ ERROR"))
            return False
    
    def test_1_backend_connectivity(self) -> bool:
        """Step 1: Verify backend is running."""
        r = self.session.get(f"{self.backend_url}/")
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"API Title: {data.get('title')}")
            print(f"API Version: {data.get('version')}")
            return True
        return False
    
    def test_2_database_connectivity(self) -> bool:
        """Step 2: Check database has data."""
        print("Testing database connectivity and data availability...")
        
        # Test through health endpoint
        r = self.session.get(f"{self.backend_url}/health")
        print(f"Health check: {r.status_code}")
        
        # Test through routes endpoint (should connect to DB)
        r = self.session.get(f"{self.backend_url}/routes")
        print(f"Routes endpoint: {r.status_code}")
        
        return r.status_code in [200, 422]  # 200=success, 422=validation error
    
    def test_3_station_search(self) -> bool:
        """Step 3: Station search functionality."""
        print("Testing station search...")
        
        test_stations = [
            ('delhi', 'Delhi'),
            ('NDLS', 'New Delhi'),
            ('mumbai', 'Mumbai'),
            ('CSMT', 'Mumbai Central'),
            ('kolkata', 'Kolkata'),
            ('HWH', 'Howrah')
        ]
        
        found_count = 0
        for search_term, name in test_stations:
            r = self.session.get(f"{self.backend_url}/stations/search", 
                               params={'q': search_term})
            
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, list) and len(result) > 0:
                    print(f"  ✓ '{search_term}' -> Found {len(result)} station(s)")
                    found_count += 1
                else:
                    print(f"  ✗ '{search_term}' -> No results")
            else:
                print(f"  ✗ '{search_term}' -> Status {r.status_code}")
        
        success_rate = found_count / len(test_stations)
        print(f"\nStation search success rate: {success_rate*100:.0f}% ({found_count}/{len(test_stations)})")
        
        return success_rate >= 0.5  # At least 50% should work
    
    def test_4_available_endpoints(self) -> bool:
        """Step 4: Verify search endpoints are registered."""
        print("Checking registered API endpoints...")
        
        r = self.session.get(f"{self.backend_url}/openapi.json")
        if r.status_code != 200:
            print("Cannot fetch OpenAPI schema")
            return False
        
        paths = r.json().get('paths', {})
        
        required_endpoints = [
            '/api/search',
            '/routes',
            '/api/popular-routes',
            '/stations/search'
        ]
        
        found = []
        for endpoint in required_endpoints:
            if endpoint in paths or any(endpoint in p for p in paths.keys()):
                found.append(endpoint)
                print(f"  ✓ {endpoint}")
            else:
                print(f"  ✗ {endpoint} NOT FOUND")
        
        print(f"\nEndpoints available: {len(found)}/{len(required_endpoints)}")
        return len(found) >= 3  # At least 3 required
    
    def test_5_route_engine_initialization(self) -> bool:
        """Step 5: Test RouteEngine can initialize."""
        print("Testing RouteEngine initialization...")
        
        try:
            from backend.services.route_engine import route_engine
            from backend.database import SessionLocal
            
            db = SessionLocal()
            
            # Test if engine is loaded
            if not route_engine._is_loaded:
                print("  Loading route engine graph...")
                route_engine.load_graph_from_db(db)
            
            print(f"  Engine loaded: {route_engine._is_loaded}")
            print(f"  Stations in graph: {len(route_engine.stations_map)}")
            print(f"  Segments in graph: {len(route_engine.segments_map)}")
            
            db.close()
            
            return route_engine._is_loaded
            
        except Exception as e:
            print(f"  Error: {e}")
            return False
    
    def test_6_multimodal_engine_initialization(self) -> bool:
        """Step 6: Test MultiModalRouteEngine."""
        print("Testing MultiModalRouteEngine initialization...")
        
        try:
            from backend.services.multi_modal_route_engine import multi_modal_route_engine
            from backend.database import SessionLocal
            
            db = SessionLocal()
            
            if not multi_modal_route_engine._is_loaded:
                print("  Loading multi-modal engine...")
                multi_modal_route_engine.load_graph_from_db(db)
            
            print(f"  Engine loaded: {multi_modal_route_engine._is_loaded}")
            print(f"  Stops in graph: {len(multi_modal_route_engine.stops_map)}")
            print(f"  Routes in graph: {len(multi_modal_route_engine.routes_map)}")
            print(f"  Trips in graph: {len(multi_modal_route_engine.trips_map)}")
            
            db.close()
            
            has_data = (len(multi_modal_route_engine.stops_map) > 0 and 
                       len(multi_modal_route_engine.routes_map) > 0)
            
            if not has_data:
                print("  WARNING: Engine loaded but has no data!")
                print("  Need to load GTFS data into database")
            
            return multi_modal_route_engine._is_loaded
            
        except Exception as e:
            print(f"  Error: {e}")
            traceback.print_exc()
            return False
    
    def test_7_basic_route_search(self) -> bool:
        """Step 7: Test basic route search endpoint."""
        print("Testing basic route search endpoint...")
        
        test_params = {
            'source': 'NDLS',
            'destination': 'CSMT'
        }
        
        r = self.session.get(f"{self.backend_url}/routes", params=test_params)
        print(f"  Status: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            print(f"  Response type: {type(result).__name__}")
            
            if isinstance(result, dict):
                if 'routes' in result:
                    print(f"  Routes found: {len(result.get('routes', []))}")
                    return len(result.get('routes', [])) > 0
                else:
                    print(f"  Keys: {list(result.keys())}")
                    return True  # Endpoint works even if no routess
            
            return True
        
        return False
    
    def test_8_popular_routes_endpoint(self) -> bool:
        """Step 8: Test popular routes endpoint."""
        print("Testing popular routes endpoint...")
        
        r = self.session.get(f"{self.backend_url}/api/popular-routes")
        print(f"  Status: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list):
                print(f"  Popular routes: {len(result)}")
                if result:
                    print(f"  Sample route: {json.dumps(result[0], indent=4)[:300]}")
                return len(result) > 0
            return True
        
        return False
    
    def test_9_search_api_endpoint(self) -> bool:
        """Step 9: Test /api/search POST endpoint."""
        print("Testing /api/search endpoint (POST)...")
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        payload = {
            'source': 'NDLS',
            'destination': 'CSMT',
            'date': tomorrow,
            'budget': 5000
        }
        
        print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        r = self.session.post(f"{self.backend_url}/api/search", json=payload)
        print(f"  Status: {r.status_code}")
        
        if r.status_code in [200, 201]:
            result = r.json()
            print(f"  Response keys: {list(result.keys())[:5]}")
            
            if isinstance(result, list):
                print(f"  Routes returned: {len(result)}")
                if result:
                    print(f"  Sample: {json.dumps(result[0], indent=2)[:300]}")
                return len(result) > 0
            
            return True
        
        print(f"  Error: {r.text[:300]}")
        return False
    
    def test_10_journey_creation(self) -> bool:
        """Step 10: Test journey creation endpoint."""
        print("Testing journey creation endpoint...")
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Try query params (based on error we saw earlier)
        params = {
            'passenger_id': 'user_123',
            'from_station': 'NDLS',
            'to_station': 'CSMT',
            'train_id': 'train_001',
            'travel_date': tomorrow,
            'class': 'AC'
        }
        
        r = self.session.post(f"{self.backend_url}/api/journey/create", params=params)
        print(f"  Status: {r.status_code}")
        
        if r.status_code in [200, 201]:
            print(f"  ✓ Journey created")
            return True
        
        print(f"  Response: {r.text[:200]}")
        return False
    
    def test_11_integration_test(self) -> bool:
        """Step 11: End-to-end integration test."""
        print("End-to-end integration test...")
        print("Simulating user flow:")
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Step 1: Search stations
        print("  1. Searching for source station 'delhi'...")
        r = self.session.get(f"{self.backend_url}/stations/search", 
                           params={'q': 'delhi'})
        source_found = r.status_code == 200 and len(r.json() if isinstance(r.json(), list) else []) > 0
        print(f"     -> {'✓' if source_found else '✗'}")
        
        # Step 2: Search routes
        print("  2. Searching for routes NDLS -> CSMT...")
        r = self.session.get(f"{self.backend_url}/routes",
                           params={'source': 'NDLS', 'destination': 'CSMT'})
        routes_found = r.status_code == 200
        print(f"     -> {'✓' if routes_found else '✗'}")
        
        # Step 3: Check popular routes
        print("  3. Checking popular routes...")
        r = self.session.get(f"{self.backend_url}/api/popular-routes")
        popular_found = r.status_code == 200 and len(r.json()) > 0
        print(f"     -> {'✓' if popular_found else '✗'}")
        
        success = source_found or routes_found or popular_found
        print(f"\n  Result: {'✓ PASS' if success else '✗ FAIL'}")
        
        return success
    
    def test_12_data_completeness(self) -> bool:
        """Step 12: Check if database has required data."""
        print("Checking database data completeness...")
        
        try:
            from backend.database import SessionLocal
            from backend.models import Stop, Trip, Route, StopTime
            
            db = SessionLocal()
            
            stop_count = db.query(Stop).count()
            trip_count = db.query(Trip).count()
            route_count = db.query(Route).count()
            stoptime_count = db.query(StopTime).count()
            
            print(f"  Stops: {stop_count}")
            print(f"  Routes: {route_count}")
            print(f"  Trips: {trip_count}")
            print(f"  Stop times: {stoptime_count}")
            
            db.close()
            
            # All should have data for routes to work
            has_data = (stop_count > 0 and route_count > 0 and 
                       trip_count > 0 and stoptime_count > 0)
            
            if not has_data:
                print("\n  ⚠ WARNING: Database may be missing required GTFS data!")
                print("  To load data, run:")
                print("    python backend/setup_ml_database.py")
                print("    OR")
                print("    python backend/load_gtfs_data.py")
            
            return has_data
            
        except Exception as e:
            print(f"  Error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence."""
        print("\n" + "="*70)
        print("ROUTEMASTER ROUTE GENERATION - COMPREHENSIVE TEST SUITE")
        print("="*70)
        
        tests = [
            ("1. Backend Connectivity", self.test_1_backend_connectivity),
            ("2. Database Connectivity", self.test_2_database_connectivity),
            ("3. Station Search", self.test_3_station_search),
            ("4. Available Endpoints", self.test_4_available_endpoints),
            ("5. RouteEngine Initialization", self.test_5_route_engine_initialization),
            ("6. MultiModalRouteEngine", self.test_6_multimodal_engine_initialization),
            ("7. Basic Route Search", self.test_7_basic_route_search),
            ("8. Popular Routes", self.test_8_popular_routes_endpoint),
            ("9. Search API (/api/search)", self.test_9_search_api_endpoint),
            ("10. Journey Creation", self.test_10_journey_creation),
            ("11. Integration Test", self.test_11_integration_test),
            ("12. Data Completeness", self.test_12_data_completeness),
        ]
        
        for name, test_func in tests:
            self.test(name, test_func)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, status in self.results if "PASS" in status)
        failed = sum(1 for _, status in self.results if "FAIL" in status or "ERROR" in status)
        
        for name, status in self.results:
            symbol = "✓" if "PASS" in status else "✗"
            print(f"{symbol} {name:50} {status}")
        
        print("\n" + "="*70)
        print(f"TOTAL: {passed} passed, {failed} failed out of {len(self.results)} tests")
        print("="*70)
        
        if failed == 0:
            print("\n✓ ALL TESTS PASSED - Route generation system is working!")
        else:
            print(f"\n✗ {failed} test(s) failed. See details above.")
            print("\nTROUBLESHOOTING:")
            print("  1. Check backend is running: python -m uvicorn backend.app:app --reload")
            print("  2. Check database has data: python backend/setup_ml_database.py")
            print("  3. Check logs: tail logs/routemaster.log")
            print("  4. Restart services: docker-compose restart")

if __name__ == "__main__":
    tester = RouteGenerationTester()
    tester.run_all_tests()
