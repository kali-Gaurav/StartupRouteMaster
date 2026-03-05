import socket
import struct
import httpx
import asyncio
import time

async def verify():
    print("--- 📡 Task 11: UDP Connection-Agnostic Fallback Verification ---")
    
    pnr = "PNR1234567" # Exactly 10 chars
    url_base = "http://localhost:8000/api/sos"
    udp_target = ("127.0.0.1", 8001)
    
    async with httpx.AsyncClient() as client:
        # 1. Trigger SOS via HTTP (to establish the session)
        print("\n[Step 1] Triggering SOS via HTTP...")
        payload = {"lat": 28.6139, "lng": 77.2090, "name": "UDP Test User", "trip": {"pnr_number": pnr}}
        res = await client.post(f"{url_base}/", json=payload)
        event_id = res.json().get("id")
        print(f"Created Event: {event_id}")
        
        # 2. Send UDP Binary Update
        print("\n[Step 2] Sending binary UDP packet (+0.05 lat change)...")
        # Format: [10 bytes PNR] [float lat] [float lng] [int timestamp]
        new_lat = 28.6639
        new_lng = 77.2090
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        packet = struct.pack('10sffi', pnr.encode('utf-8'), new_lat, new_lng, int(time.time()))
        sock.sendto(packet, udp_target)
        sock.close()
        
        # 3. Wait for processing
        print("Waiting for UDP worker processing...")
        await asyncio.sleep(5)
        
        # 4. Verify via API
        print("\n[Step 3] Fetching event to verify UDP update...")
        res_get = await client.get(f"{url_base}/{event_id}")
        event = res_get.json()
        
        if event and abs(event.get('lat', 0) - new_lat) < 0.001:
            print(f"✅ SUCCESS: Coordinates updated via UDP to {event['lat']}, {event['lng']}")
            print("\n🏆 TASK 11 VERIFIED: Connection-agnostic UDP fallback is operational.")
        else:
            print(f"❌ FAILURE: Coordinates mismatch. Got {event.get('lat')}, expected {new_lat}.")

if __name__ == "__main__":
    asyncio.run(verify())
