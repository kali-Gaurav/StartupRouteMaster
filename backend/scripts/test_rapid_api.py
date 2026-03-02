import os
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv('backend/.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RapidAPITest")

async def test_rapid_api_connection():
    api_key = os.getenv("RAPIDAPI_KEY")
    api_host = "irctc1.p.rapidapi.com"
    base_url = f"https://{api_host}/api/v1"
    
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host
    }
    
    # Test 1: Search Train
    logger.info("Testing RapidAPI Connection (Search Train)...")
    search_url = f"{base_url}/searchTrain"
    params = {"query": "12002"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, headers=headers, params=params) as resp:
                status = resp.status
                data = await resp.json()
                if status == 200:
                    logger.info(f"✅ Connection Successful! HTTP {status}")
                    logger.info(f"Response Status: {data.get('status')}")
                    if data.get('data'):
                        logger.info("✅ Data received correctly.")
                    else:
                        logger.warning("⚠️ Connected but no data received. Check if API is active for seat availability.")
                else:
                    logger.error(f"❌ Connection Failed! HTTP {status}")
                    logger.error(f"Error Detail: {data}")
        except Exception as e:
            logger.error(f"❌ Request Error: {e}")

    # Test 2: Seat Availability (Real Check)
    logger.info("\nTesting Seat Availability API specifically...")
    avail_url = f"{base_url}/checkSeatAvailability"
    # Using 12002 (Shatabdi) NDLS to AGC
    avail_params = {
        "trainNo": "12002",
        "fromStationCode": "NDLS",
        "toStationCode": "AGC",
        "date": "10-03-2026",
        "quota": "GN",
        "classType": "CC"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(avail_url, headers=headers, params=avail_params) as resp:
                status = resp.status
                data = await resp.json()
                if status == 200:
                    if data.get('status'):
                        logger.info("✅ Seat Availability API is WORKING.")
                        logger.info(f"Result: {data.get('message', 'No message')}")
                    else:
                        logger.warning(f"⚠️ API returned status False. Message: {data.get('message')}")
                else:
                    logger.error(f"❌ Seat API Failed! HTTP {status}")
                    logger.error(f"Response: {data}")
        except Exception as e:
            logger.error(f"❌ Request Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_rapid_api_connection())
