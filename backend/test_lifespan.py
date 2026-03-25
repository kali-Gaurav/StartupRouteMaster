import asyncio
import logging
import time
from fastapi import FastAPI
from core.lifespan import lifespan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_lifespan")

async def test_lifespan():
    app = FastAPI()
    print("--- Starting Lifespan Test ---")
    start = time.time()
    
    async with lifespan(app):
        print(f"--- Lifespan context entered in {time.time() - start:.3f}s ---")
        print("Waiting 5 seconds inside lifespan...")
        await asyncio.sleep(5)
        print("Exiting lifespan context...")
    
    print(f"--- Lifespan test complete in {time.time() - start:.3f}s ---")

if __name__ == "__main__":
    try:
        asyncio.run(test_lifespan())
    except Exception as e:
        print(f"Lifespan failed: {e}")
        import traceback
        traceback.print_exc()
