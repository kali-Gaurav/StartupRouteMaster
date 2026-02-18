#!/usr/bin/env python3
"""Quick test script to verify backend and frontend are working."""

import requests
import time
import subprocess
import sys

def test_backend():
    """Test if backend is running and responding."""
    print("\n" + "="*60)
    print("BACKEND TEST")
    print("="*60)
    
    try:
        # Test root endpoint
        r = requests.get('http://localhost:8000/', timeout=5)
        if r.status_code == 200:
            print("✓ Backend running at http://localhost:8000")
            data = r.json()
            print(f"  - Title: {data.get('title')}")
            print(f"  - Version: {data.get('version')}")
        else:
            print("✗ Backend returned status:", r.status_code)
            return False
            
        # Test routes endpoint
        r = requests.get('http://localhost:8000/routes', params={'source': 'NDLS', 'destination': 'CSMT'}, timeout=5)
        if r.status_code == 200:
            print("✓ Routes endpoint working")
            result = r.json()
            print(f"  - Response type: {type(result)}")
        else:
            print("✗ Routes endpoint failed:", r.status_code)
            
        # Test health endpoint
        r = requests.get('http://localhost:8000/health', timeout=5)
        if r.status_code == 200:
            print("✓ Health check passed")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to backend at localhost:8000")
        print("  Make sure to run: python -m uvicorn backend.app:app --reload")
        return False
    except Exception as e:
        print(f"✗ Backend test error: {e}")
        return False

def test_frontend():
    """Test if frontend is running."""
    print("\n" + "="*60)
    print("FRONTEND TEST")
    print("="*60)
    
    try:
        r = requests.get('http://localhost:5173/', timeout=5)
        if r.status_code == 200:
            print("✓ Frontend running at http://localhost:5173")
            return True
        else:
            print("✗ Frontend returned status:", r.status_code)
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to frontend at localhost:5173")
        print("  Make sure to run: npm run dev")
        return False
    except Exception as e:
        print(f"✗ Frontend test error: {e}")
        return False

def test_cors():
    """Test CORS configuration."""
    print("\n" + "="*60)
    print("CORS TEST")
    print("="*60)
    
    try:
        headers = {
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'GET'
        }
        r = requests.options('http://localhost:8000/routes', headers=headers, timeout=5)
        
        if 'Access-Control-Allow-Origin' in r.headers:
            print("✓ CORS enabled")
            print(f"  - Allow-Origin: {r.headers.get('Access-Control-Allow-Origin')}")
        else:
            print("✗ CORS not properly configured")
            return False
            
        return True
    except Exception as e:
        print(f"✗ CORS test error: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("RouteMaster System Verification".center(60))
    print("="*60)
    
    backend_ok = test_backend()
    frontend_ok = test_frontend()
    cors_ok = test_cors() if backend_ok and frontend_ok else False
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    status = {
        "Backend": "✓" if backend_ok else "✗",
        "Frontend": "✓" if frontend_ok else "✗",
        "CORS": "✓" if cors_ok else "N/A"
    }
    
    for service, check in status.items():
        print(f"{service:15} {check}")
    
    print("\n" + "="*60)
    if backend_ok and frontend_ok:
        print("✓ System ready! Open http://localhost:5173 in browser")
    else:
        print("✗ Some services are not running")
        print("\nTo start services:")
        print("1. Backend: python -m uvicorn backend.app:app --reload")
        print("2. Frontend: npm run dev")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
