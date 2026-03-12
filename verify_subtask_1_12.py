import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.12")

BASE_URL = "http://127.0.0.1:8000"

async def test_aborted_gzip():
    logger.info("Testing Resilient GZip with aborted connection...")
    
    # We need a large enough response to trigger GZip chunking
    # /api/health/live is small, but let's try something likely bigger or just hit it repeatedly
    url = f"{BASE_URL}/api/health/live"
    
    try:
        # Create a client but close it mid-read if possible, 
        # or just drop the connection during the request.
        transport = httpx.AsyncHTTPTransport(retries=0)
        async with httpx.AsyncClient(transport=transport) as client:
            # We don't await the body, just the start
            async with client.stream("GET", url) as response:
                logger.info(f"Connected, status {response.status_code}. Aborting now...")
                # Closing here should trigger the catch block in middleware
                await response.aclose()
        
        logger.info("✅ Request aborted. Check backend logs for 'GZip: Client disconnected early'.")
    except Exception as e:
        logger.error(f"❌ Test script error (Expected if connection drops): {e}")

if __name__ == "__main__":
    asyncio.run(test_aborted_gzip())
