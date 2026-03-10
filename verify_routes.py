import requests
import sys

BASE_URL = "http://localhost:8000"

def check_endpoint(path):
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, timeout=5)
        print(f"GET {url} -> {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"GET {url} -> Failed: {e}")

if __name__ == "__main__":
    print("Verifying Backend Routes...")
    check_endpoint("/api/health")
    check_endpoint("/api/health/live")
    check_endpoint("/api/stats")
    check_endpoint("/health")
