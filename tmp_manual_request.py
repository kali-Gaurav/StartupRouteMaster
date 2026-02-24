import logging
from backend.app import app
from fastapi.testclient import TestClient
from backend.core.route_engine import route_engine

# suppress SQL logs
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)

async def dummy_search(*args, **kwargs):
    return []
route_engine.search_routes = dummy_search

# also patch SearchService to avoid hitting database during unlock-details
from backend.services.search_service import SearchService

async def fake_unlock(self, journey_id, travel_date_str, coach_preference="AC_THREE_TIER", passenger_age=30, concession_type=None):
    return {
        "journey": {
            "journey_id": journey_id,
            "num_segments": 1,
            "distance_km": 100.0,
            "travel_time": "02:00",
            "num_transfers": 0,
            "is_direct": True,
            "cheapest_fare": 500.0,
            "premium_fare": 1100.0,
            "has_overnight": False,
            "availability_status": "AVAILABLE"
        },
        "segments": [],
        "seat_allocation": {},
        "verification": {},
        "fare_breakdown": {},
        "can_unlock_details": True,
        "route_graph": {"nodes": [], "edges": [], "is_direct": True},
        "verification_summary": {"rapidapi_calls": 0, "seat_availability": {}, "fare_verification": {}, "warnings": []}
    }

SearchService.unlock_journey_details = fake_unlock

with TestClient(app) as client:
    resp = client.get('/api/v2/journey/test_journey/unlock-details', params={'travel_date':'2026-03-01'})
    print('status',resp.status_code)
    try:
        print('json',resp.json())
    except Exception:
        print('text',resp.text)
