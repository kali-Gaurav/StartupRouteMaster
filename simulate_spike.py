import requests
import time

def simulate_spike():
    url = "http://127.0.0.1:8000/api/v2/search/routes" # Adjust to your actual search endpoint
    payload = {"source": "DEL", "destination": "MUM", "travel_date": "2026-05-01"}
    headers = {"Authorization": "Bearer dev-bypass", "X-Dev-Bypass": "TRUE"}
    
    print("🚀 Triggering artificial demand spike (50 requests)...")
    for i in range(50):
        try:
            requests.post(url, json=payload, headers=headers)
        except Exception:
            pass
    print("✅ Spike injected. Check Redis Heatmap in 30 seconds.")

if __name__ == "__main__":
    simulate_spike()
