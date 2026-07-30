import asyncio
import logging
import sys
import os
from datetime import datetime

# Add parent directory to sys.path to allow importing from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.rapidapi_provider import rapidapi_provider
from database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_endpoints():
    logger.info("🚀 Starting RapidAPI Endpoints Verification...")
    
    # Initialize the provider
    await rapidapi_provider.init()
    
    if not rapidapi_provider.is_healthy:
        logger.error("❌ RapidAPI Provider failed to initialize. Check your API key and host.")
        return

    test_train = "19038"
    test_from = "ST"
    test_to = "BVI"
    test_date = "2026-03-24" # Tomorrow or some future date
    test_pnr = "1234567890"

    endpoints_to_test = [
        ("get_train_schedule", [test_train]),
        ("get_train_schedule_v2", [test_train]),
        ("get_live_train_status", [test_train, 1]),
        ("get_live_station", [test_from, 1]),
        ("get_trains_between_stations", [test_from, test_to]),
        ("get_trains_between_stations_v3", [test_from, test_to]),
        ("get_fare", [test_train, test_from, test_to]),
        ("get_fare_v2", [test_train, test_from, test_to]),
        ("check_seat_availability", [test_train, test_from, test_to, test_date, "2A", "GN"]),
        ("check_seat_availability_v1", [test_train, test_from, test_to, test_date, "2A", "GN"]),
        ("get_pnr_status", [test_pnr]),
        ("get_pnr_status_v2", [test_pnr]),
        ("get_pnr_status_detail", [test_pnr]),
        ("get_train_classes", [test_train]),
        ("search_station", ["BJU"]),
        ("search_train", ["190"]),
        ("get_trains_by_station", [test_from]),
    ]

    results = {}

    for method_name, args in endpoints_to_test:
        logger.info(f"Testing {method_name} with args {args}...")
        try:
            method = getattr(rapidapi_provider, method_name)
            res = await method(*args)
            if res:
                logger.info(f"✅ {method_name} SUCCESS")
                results[method_name] = "SUCCESS"
            else:
                logger.warning(f"⚠️ {method_name} returned None (likely API error or empty data)")
                results[method_name] = "NONE"
        except Exception as e:
            logger.error(f"❌ {method_name} FAILED: {e}")
            results[method_name] = f"FAILED: {e}"

    logger.info("\n--- Verification Summary ---")
    for method, result in results.items():
        logger.info(f"{method}: {result}")
    
    await rapidapi_provider.shutdown()

if __name__ == "__main__":
    asyncio.run(verify_endpoints())
