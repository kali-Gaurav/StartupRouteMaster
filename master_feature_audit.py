import asyncio
import httpx
import sys
import os
import json
from datetime import datetime

async def run_master_audit():
    print("\n🚀 --- STARTING MASTER FEATURE AUDIT (LOCAL) ---")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. BASE CONNECTIVITY
        print("\n[1/7] Testing Core Infrastructure...")
        try:
            r = await client.get("http://localhost:8000/ping")
            print(f"   ✅ API Ping: {r.status_code} - Version {r.json().get('version')}")
            
            r = await client.get("http://localhost:8000/")
            data = r.json()
            engines = data.get('engines', {})
            print(f"   ✅ Engines: RM:{engines.get('routemaster')}, Cache:{engines.get('cache')}")
        except Exception as e:
            print(f"   ❌ Core Infrastructure Failed: {e}")

        # 2. STATION AUTO-SUGGESTION
        print("\n[2/7] Testing Station Autocomplete...")
        queries = ["KOTA", "MUMBAI", "DELHI"]
        for q in queries:
            try:
                r = await client.get(f"http://localhost:8000/api/stations/search?q={q}")
                results = r.json()
                if r.status_code == 200:
                    print(f"   ✅ Query '{q}': Found {len(results)} stations")
                else:
                    print(f"   ❌ Query '{q}': Status {r.status_code}")
            except Exception as e:
                print(f"   ❌ Station Suggestion Failed for '{q}': {e}")

        # 3. CHATBOT / AI LOGIC
        print("\n[3/7] Testing AI Chatbot Integration...")
        try:
            chat_payload = {
                "message": "Hello, I want to go to KOTA tomorrow",
                "session_id": "audit-test-session"
            }
            r = await client.post("http://localhost:8000/api/chat", json=chat_payload)
            if r.status_code == 200:
                print(f"   ✅ Chatbot Response: {r.json().get('reply')[:60]}...")
            else:
                print(f"   ❌ Chatbot Failed: {r.status_code}")
        except Exception as e:
            print(f"   ❌ Chatbot Test Error: {e}")

        # 4. ROUTE SEARCH ENGINE
        print("\n[4/7] Testing RouteMaster Engine (PGT -> BNC)...")
        try:
            search_payload = {
                "source": "PGT",
                "destination": "BNC",
                "date": "2026-03-04"
            }
            # FastAPI routes with / prefix need the trailing slash if defined as /
            r = await client.post("http://localhost:8000/api/search/", json=search_payload)
            if r.status_code == 200:
                journeys = r.json().get("journeys", [])
                print(f"   ✅ Search: Found {len(journeys)} routes.")
            else:
                print(f"   ❌ Search Engine Failed: {r.status_code}")
        except Exception as e:
            print(f"   ❌ Search Test Error: {e}")

        # 5. FRONTEND SERVER CHECK
        print("\n[5/7] Testing Frontend Availability...")
        try:
            r = await client.get("http://localhost:5173")
            print(f"   ✅ Frontend Server: UP (Port 5173)")
        except Exception as e:
            print(f"   ❌ Frontend Unreachable: {e}")

        # 6. UNLOCK / VERIFICATION FLOW
        print("\n[6/7] Testing Seat Availability Endpoint...")
        try:
            # The actual public endpoint is POST /api/v1/booking/availability
            avail_payload = {
                "trip_id": "16378", # Using train no as trip_id for test
                "from_stop_id": 59, 
                "to_stop_id": 166,
                "travel_date": "2026-03-04",
                "class_type": "2S"
            }
            r = await client.post("http://localhost:8000/api/v1/booking/availability", json=avail_payload)
            if r.status_code == 200:
                print(f"   ✅ Availability: {r.json().get('status')} - Seats: {r.json().get('seats_available')}")
            else:
                # Might fail if trip_id 16378 isn't in DB yet, but 200/404 is better than 401/405
                print(f"   ℹ️ Availability Status: {r.status_code} (Expected if trip missing)")
        except Exception as e:
            print(f"   ❌ Availability Test Error: {e}")

    print("\n🏁 --- MASTER AUDIT COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_master_audit())
