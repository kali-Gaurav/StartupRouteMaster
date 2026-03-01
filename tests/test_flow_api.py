import asyncio
import httpx
from fastapi import FastAPI
from api.flow import router
import uvicorn
import threading
import time

app = FastAPI()
app.include_router(router)

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8005, log_level="error")

async def test_flow():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    async with httpx.AsyncClient() as client:
        print("Testing POST /api/flow/ack")
        resp = await client.post(
            "http://127.0.0.1:8005/api/flow/ack", 
            json={"correlation_id": "test_flow_1", "event": "UI_LOADED"}
        )
        print(f"Status: {resp.status_code}")
        
        resp = await client.post(
            "http://127.0.0.1:8005/api/flow/ack", 
            json={"correlation_id": "test_flow_1", "event": "PAYMENT_CONFIRMED"}
        )
        print(f"Status: {resp.status_code}")

        print("Testing GET /api/flow/status")
        resp = await client.get("http://127.0.0.1:8005/api/flow/status")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(resp.json())

if __name__ == "__main__":
    asyncio.run(test_flow())
