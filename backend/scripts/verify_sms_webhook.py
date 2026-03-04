import httpx
import asyncio
import json

async def test_sms_webhook():
    url = "http://localhost:8000/api/sos/sms-webhook"
    print("--- Offline SMS Parser Verification ---")
    
    # 1. Mock SMS Payload (Twilio Format)
    payload = {
        "Body": "EMERGENCY SOS: Help requested at 28.6428, 77.2190. Please help me!",
        "From": "+919876543210"
    }
    
    print(f"\n[Test] Sending mock SMS to webhook...")
    async with httpx.AsyncClient() as client:
        try:
            # Note: request.form() expects multipart/form-data or application/x-www-form-urlencoded
            response = await client.post(url, data=payload, timeout=10.0)
            
            print(f"Status: {response.status_code}")
            data = response.json()
            
            if response.status_code == 200 and data.get("status") == "active":
                print(f"[PASS] SMS parsed correctly. Lat: {data['lat']}, Lng: {data['lng']}")
                print(f"Maps URL: {data['google_maps_url']}")
            else:
                print(f"[FAIL] SMS parsing failed. Data: {data}")
                
        except Exception as e:
            print(f"Error: {e}")
            print("Note: Ensure the backend server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_sms_webhook())
