import httpx
import asyncio
import time

async def verify():
    print("--- 📑 Automated Incident Reporting Verification ---")
    
    # 1. Trigger an SOS to have an event
    print("\n[Step 1] Triggering an SOS...")
    trigger_url = "http://localhost:8000/api/sos/"
    payload = {
        "lat": 19.0760, "lng": 72.8777,
        "name": "Reporting Test User",
        "phone": "+91-1234567890",
        "extra": "Testing Task 37 reporting logic.",
        "trip": {"vehicle_number": "12134", "coach": "A1"}
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(trigger_url, json=payload)
        event_id = res.json().get("id")
        print(f"Created Event ID: {event_id}")
        
        # 2. Add some fake logs
        # (Internal load/save is used by report, so we assume process_sos enriched it)
        
        # 3. Fetch the report
        print(f"\n[Step 2] Fetching report for {event_id}...")
        report_url = f"http://localhost:8000/api/sos/{event_id}/report"
        report_res = await client.get(report_url)
        
        if report_res.status_code == 200:
            print("\n--- REPORT CONTENT ---")
            print(report_res.text)
            print("--- END REPORT ---")
            
            if "Passenger Information" in report_res.text and "Trip Context" in report_res.text:
                print("\n🏆 INCIDENT REPORTING VERIFIED: Summary generated successfully.")
            else:
                print("\n❌ INCIDENT REPORTING FAILED: Summary content missing sections.")
        else:
            print(f"\n❌ INCIDENT REPORTING FAILED: Status {report_res.status_code}")

if __name__ == "__main__":
    time.sleep(3)
    asyncio.run(verify())