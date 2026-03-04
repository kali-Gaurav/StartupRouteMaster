import asyncio
import websockets
import json
import sys

async def test_chat_ws():
    uri = "ws://localhost:8000/api/chat/ws"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Test Local Intent (Instant)
            print("\n--- Testing Local Intent (Instant) ---")
            msg = {"message": "NDLS to BCT", "session_id": "test-session-123"}
            await websocket.send(json.dumps(msg))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received Final: {data.get('reply')}")

            # 2. Test LLM Streaming
            print("\n--- Testing LLM Streaming (Real-time) ---")
            msg = {"message": "Tell me a very short joke about trains.", "session_id": "test-session-123"}
            await websocket.send(json.dumps(msg))
            
            print("Streaming tokens: ", end="", flush=True)
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data["type"] == "token":
                    print(data["token"], end="", flush=True)
                elif data["type"] == "final":
                    print(f"\nFinal Reply: {data['reply']}")
                    break
                elif data["type"] == "error":
                    print(f"\nError: {data['message']}")
                    break
                    
    except Exception as e:
        print(f"\nConnection failed: {e}")
        print("Note: Ensure the backend server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_chat_ws())
