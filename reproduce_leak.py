import asyncio
import logging
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.realtime_ingestion.api_client import AsyncRappidAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reproduce_leak():
    logger.info("Starting leak reproduction...")
    # Instantiate without closing
    client = AsyncRappidAPIClient()
    await client.fetch_train_status("12345")
    # client.close() is NOT called
    
    logger.info("Client leaked (hopefully).")

if __name__ == "__main__":
    asyncio.run(reproduce_leak())
    logger.info("Script finished. Check for 'Unclosed client session' warnings.")
