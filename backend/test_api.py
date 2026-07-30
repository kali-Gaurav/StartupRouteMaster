import urllib.request
import json
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/search/',
    data=b'{"source": "NDLS", "destination": "BCT", "travel_date": "2026-05-15", "max_transfers": 3, "persona": "comfort"}',
    headers={'Content-Type': 'application/json'}
)
try:
    print(urllib.request.urlopen(req).read().decode())
except Exception as e:
    print("Error:", e)
