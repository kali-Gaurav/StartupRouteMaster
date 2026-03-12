import asyncio
import httpx
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.6")

BASE_URL = "http://127.0.0.1:8000"

async def test_streaming_search():
    logger.info("Testing SSE Stream with Standardized Error Handling...")
    url = f"{BASE_URL}/api/v2/search/stream?source=KOTA&destination=NDLS&date=2026-03-15"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("GET", url) as response:
                logger.info(f"Received Content-Type: {response.headers.get('content-type')}")
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                
                count = 0
                async for line in response.aiter_lines():
                    if line.strip():
                        print(f"RAW: {line}")
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        logger.info(f"Received chunk status: {data.get('status')} - count: {count}")
                        count += 1
                        if data.get("status") == "complete" or data.get("status") == "error":
                            break
                
                assert count > 0
                logger.info(f"✅ Stream verified. Received {count} chunks.")
        except Exception as e:
            logger.error(f"❌ Stream test failed: {e}")
            raise e

if __name__ == "__main__":
    asyncio.run(test_streaming_search())
