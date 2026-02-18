#!/usr/bin/env python3
"""Test route generation from backend."""

import requests
import json

def test_route_generation():
    """Test if routes are being generated."""
    url = 'http://localhost:8000/api/search'
    payload = {
        'source': 'NDLS',
        'destination': 'CSMT',
        'date': '2024-02-25',
        'budget': 5000
    }
    
    print("=" * 60)
    print("ROUTE GENERATION TEST")
    print("=" * 60)
    print(f"\nEndpoint: POST {url}")
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2))
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"\nStatus Code: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            print("\n✓ Routes endpoint responded successfully!")
            
            if isinstance(result, dict):
                print(f"Response keys: {list(result.keys())}")
                if 'routes' in result:
                    routes = result['routes']
                    print(f"Total routes found: {len(routes)}")
                    if routes:
                        print(f"\nFirst route sample:")
                        print(json.dumps(routes[0], indent=2)[:1000])
            elif isinstance(result, list):
                print(f"Total routes found: {len(result)}")
                if result:
                    print(f"\nFirst route sample:")
                    print(json.dumps(result[0], indent=2)[:1000])
        else:
            print(f"✗ Error: Status {r.status_code}")
            print(f"Response:\n{r.text[:500]}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Backend not running at localhost:8000")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    test_route_generation()
