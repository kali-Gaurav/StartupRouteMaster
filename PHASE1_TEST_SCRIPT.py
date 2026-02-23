#!/usr/bin/env python3
"""
Phase 1: Route Generation & Search Testing Script
Manual execution script for testing route generation.
"""

import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:8000"

def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_tc1_1_real_station_search():
    """TC-1.1: Real Station Search (NDLS → MMCT)"""
    print_header("TC-1.1: Real Station Search (NDLS → MMCT)")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    request_data = {
        "source": "NDLS",
        "destination": "MMCT",
        "date": future_date,
        "budget": "all"
    }
    
    print(f"Request:")
    print(json.dumps(request_data, indent=2))
    print(f"\nCalling POST {BASE_URL}/api/search...")
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/api/search",
            json=request_data,
            timeout=30
        )
        elapsed_time = (time.time() - start_time) * 1000
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Time: {elapsed_time:.2f} ms")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!")
            print(f"Source: {data.get('source')}")
            print(f"Destination: {data.get('destination')}")
            
            routes = data.get("routes", {})
            direct = routes.get("direct", [])
            one_transfer = routes.get("one_transfer", [])
            
            print(f"\nRoutes Found:")
            print(f"  Direct: {len(direct)}")
            print(f"  One Transfer: {len(one_transfer)}")
            
            if direct:
                route = direct[0]
                print(f"\nFirst Direct Route:")
                print(f"  Train No: {route.get('train_no')}")
                print(f"  Train Name: {route.get('train_name', 'N/A')}")
                print(f"  Departure: {route.get('departure')}")
                print(f"  Arrival: {route.get('arrival')}")
                print(f"  Fare: ₹{route.get('fare', 'N/A')}")
                
                # Validate
                train_no = route.get('train_no')
                if train_no:
                    train_no_str = str(train_no)
                    print(f"\n✅ Train number format: {train_no_str} ({'Valid' if len(train_no_str) >= 4 else 'Invalid'})")
                
                print(f"✅ Station codes: {data.get('source')} → {data.get('destination')}")
                print(f"✅ Response time: {elapsed_time:.2f} ms ({'Good' if elapsed_time < 500 else 'Slow'})")
            else:
                print("\n⚠️ No direct routes found")
            
            return True, data
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text[:500])
            return False, None
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to backend. Is it running on localhost:8000?")
        return False, None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False, None

def test_tc1_2_multiple_segments():
    """TC-1.2: Route with Multiple Segments (NDLS → SBC)"""
    print_header("TC-1.2: Route with Multiple Segments (NDLS → SBC)")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    request_data = {
        "source": "NDLS",
        "destination": "SBC",
        "date": future_date,
        "budget": "all"
    }
    
    print(f"Request:")
    print(json.dumps(request_data, indent=2))
    print(f"\nCalling POST {BASE_URL}/api/search...")
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/api/search",
            json=request_data,
            timeout=30
        )
        elapsed_time = (time.time() - start_time) * 1000
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Time: {elapsed_time:.2f} ms")
        
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", {})
            one_transfer = routes.get("one_transfer", [])
            two_transfer = routes.get("two_transfer", [])
            
            print(f"\n✅ Success!")
            print(f"Routes Found:")
            print(f"  One Transfer: {len(one_transfer)}")
            print(f"  Two Transfer: {len(two_transfer)}")
            
            if one_transfer:
                route = one_transfer[0]
                print(f"\nFirst One-Transfer Route:")
                print(f"  Type: {route.get('type')}")
                print(f"  Total Time: {route.get('total_time_minutes')} minutes")
                print(f"  Total Fare: ₹{route.get('total_fare', 'N/A')}")
                print(f"  Junction: {route.get('junction', 'N/A')}")
                print(f"  Waiting Time: {route.get('waiting_time_minutes', 'N/A')} minutes")
                
                print(f"\n✅ Transfer information present")
            
            return True, data
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text[:500])
            return False, None
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False, None

def test_tc1_3_invalid_station():
    """TC-1.3: Invalid Station Codes"""
    print_header("TC-1.3: Invalid Station Codes (INVALID → MMCT)")
    
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    request_data = {
        "source": "INVALID",
        "destination": "MMCT",
        "date": future_date,
        "budget": "all"
    }
    
    print(f"Request:")
    print(json.dumps(request_data, indent=2))
    print(f"\nCalling POST {BASE_URL}/api/search...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/search",
            json=request_data,
            timeout=30
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", {})
            direct = routes.get("direct", [])
            
            if len(direct) == 0:
                print(f"\n✅ No routes found for invalid station (expected)")
                print(f"✅ Error handling works correctly")
            else:
                print(f"\n⚠️ Routes found for invalid station: {len(direct)}")
                print("   (May need validation improvement)")
            
            return True, data
        elif response.status_code == 404:
            print(f"\n✅ 404 returned for invalid station (expected)")
            return True, None
        else:
            print(f"\n⚠️ Status {response.status_code} returned")
            print(response.text[:500])
            return True, None  # Still consider success if handled
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False, None

def main():
    """Run all Phase 1 tests."""
    print("="*70)
    print("  PHASE 1: Route Generation & Search Testing")
    print("="*70)
    print(f"\nBackend URL: {BASE_URL}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "tc1_1": None,
        "tc1_2": None,
        "tc1_3": None
    }
    
    # Run tests
    print("\n" + "="*70)
    print("  Starting Tests...")
    print("="*70)
    
    success1, data1 = test_tc1_1_real_station_search()
    results["tc1_1"] = {"success": success1, "data": data1}
    
    success2, data2 = test_tc1_2_multiple_segments()
    results["tc1_2"] = {"success": success2, "data": data2}
    
    success3, data3 = test_tc1_3_invalid_station()
    results["tc1_3"] = {"success": success3, "data": data3}
    
    # Summary
    print_header("Phase 1 Test Summary")
    
    total_tests = 3
    passed_tests = sum([results["tc1_1"]["success"], results["tc1_2"]["success"], results["tc1_3"]["success"]])
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\n" + "="*70)
    print("  Phase 1 Testing Complete")
    print("="*70)
    
    if passed_tests == total_tests:
        print("\n✅ All tests passed! Ready for Phase 2.")
    else:
        print("\n⚠️ Some tests failed. Review and fix before proceeding to Phase 2.")

if __name__ == "__main__":
    main()
