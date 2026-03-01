import asyncio
import httpx
from fastapi import FastAPI, Depends
import uvicorn
import threading
import time
import os
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from api.search import router as search_router
from api.payments import router as payments_router
from api.bookings import router as bookings_router
from api.dependencies import get_current_user
from database.session import SessionLocal
from database.models import User

app = FastAPI()

# 1. Mock Authentication
async def mock_get_current_user():
    db = SessionLocal()
    # Use the existing user ID found earlier
    user = db.query(User).filter(User.id == "e094b06a-154e-434e-9536-618f2f0a79c1").first()
    db.close()
    return user

app.dependency_overrides[get_current_user] = mock_get_current_user

app.include_router(search_router)
app.include_router(payments_router)
app.include_router(bookings_router)

@app.on_event("startup")
async def startup():
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8020, log_level="error")

async def test_full_pipeline():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(3) # Give more time for initialization

    async with httpx.AsyncClient(timeout=60.0) as client:
        print("\n=== STEP 1: Search for Routes (KOTA -> NDLS) ===")
        search_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        resp = await client.get(f"http://127.0.0.1:8020/api/search/quick?source=KOTA&destination=NDLS&date={search_date}")
        print(f"Search Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.text}")
            return
        
        results = resp.json()
        routes = results.get("routes", [])
        print(f"Found {len(routes)} routes.")
        if not routes:
            print("No routes found, cannot continue.")
            return
        
        target_route = routes[0]
        route_id = target_route["journey_id"]
        train_no = target_route["legs"][0]["train_number"]
        print(f"Selected Route: {route_id}, Train: {train_no}")

        print("\n=== STEP 2: Create Unlock Payment Session ===")
        resp = await client.post(
            "http://127.0.0.1:8020/api/payments/create_session",
            json={"journey_id": route_id, "amount": 39.0}
        )
        print(f"Create Session Status: {resp.status_code}")
        session_data = resp.json()
        session_code = session_data["session_code"]
        print(f"Session Code: {session_code}")

        print("\n=== STEP 3: Confirm Payment (Manual) ===")
        resp = await client.post(
            "http://127.0.0.1:8020/api/payments/confirm_manual",
            json={"session_code": session_code, "journey_id": route_id}
        )
        print(f"Confirm Status: {resp.status_code}")
        print(f"Message: {resp.json().get('message')}")

        print("\n=== STEP 4: Create Final Booking Request (With RapidAPI Seat Check) ===")
        # Prepare payload
        booking_payload = {
            "route_id": route_id,
            "source_station": "KOTA",
            "destination_station": "NDLS",
            "from_station_code": "KOTA",
            "to_station_code": "NDLS",
            "journey_date": search_date,
            "train_number": train_no,
            "class_type": "3A",
            "quota": "GN",
            "passengers": [
                {"name": "Test Passenger", "age": 30, "gender": "M"}
            ]
        }
        
        start_verify = time.time()
        resp = await client.post(
            "http://127.0.0.1:8020/api/v1/booking/request",
            json=booking_payload
        )
        verify_duration = (time.time() - start_verify) * 1000
        
        print(f"Booking Request Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Booking ID: {data['id']}")
            print(f"Verification Status: {data['verification_status']}")
            print(f"Queue Status: {data['queue_status']}")
            print(f"Time taken for final check: {verify_duration:.2f}ms")
        else:
            print(f"Error: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
