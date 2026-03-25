import asyncio
import logging
from services.rapidapi_provider import rapidapi_provider

# Configure logging to see output
logging.basicConfig(level=logging.INFO)

async def test_all_endpoints():
    print("--- Testing All Endpoints ---")
    await rapidapi_provider.init()

    # Test get_fare
    print("--- Testing get_fare ---")
    fare_result = await rapidapi_provider.get_fare(train_no="19038", from_station="bvi", to_station="st")
    print("✅ get_fare successful:" if fare_result else "❌ get_fare failed.")
    if fare_result: print(fare_result.model_dump_json(indent=2))

    # Test get_trains_between_stations
    print("--- Testing get_trains_between_stations ---")
    trains_result = await rapidapi_provider.get_trains_between_stations(from_station_code="bju", to_station_code="bdts")
    print("✅ get_trains_between_stations successful:" if trains_result else "❌ get_trains_between_stations failed.")
    if trains_result: print(trains_result.model_dump_json(indent=2))

    # Test get_pnr_status
    print("--- Testing get_pnr_status ---")
    pnr_result = await rapidapi_provider.get_pnr_status(pnr="1234567890") # Dummy PNR
    print("✅ get_pnr_status successful:" if pnr_result else "❌ get_pnr_status failed.")
    if pnr_result: print(pnr_result.model_dump_json(indent=2))

    # Test search_station
    print("--- Testing search_station ---")
    station_result = await rapidapi_provider.search_station(query="BJU")
    print("✅ search_station successful:" if station_result else "❌ search_station failed.")
    if station_result: print(station_result.model_dump_json(indent=2))

    # Test search_train
    print("--- Testing search_train ---")
    train_search_result = await rapidapi_provider.search_train(query="190")
    print("✅ search_train successful:" if train_search_result else "❌ search_train failed.")
    if train_search_result: print(train_search_result.model_dump_json(indent=2))

    # Test get_train_schedule
    print("--- Testing get_train_schedule ---")
    schedule_result = await rapidapi_provider.get_train_schedule(train_no="12936")
    print("✅ get_train_schedule successful:" if schedule_result else "❌ get_train_schedule failed.")
    if schedule_result: print(schedule_result.model_dump_json(indent=2))

    # Test check_seat_availability
    print("--- Testing check_seat_availability ---")
    availability_result = await rapidapi_provider.check_seat_availability(train_no="19038", from_station="st", to_station="bvi", date="2026-03-25", class_type="2A", quota="GN")
    print("✅ check_seat_availability successful:" if availability_result else "❌ check_seat_availability failed.")
    if availability_result: print(availability_result.model_dump_json(indent=2))

    # Test get_train_classes
    print("--- Testing get_train_classes ---")
    classes_result = await rapidapi_provider.get_train_classes(train_no="19038")
    print("✅ get_train_classes successful:" if classes_result else "❌ get_train_classes failed.")
    if classes_result: print(classes_result.model_dump_json(indent=2))

    # Test get_live_station
    print("--- Testing get_live_station ---")
    live_station_result = await rapidapi_provider.get_live_station(station_code="NDLS", hours=1)
    print("✅ get_live_station successful:" if live_station_result else "❌ get_live_station failed.")
    if live_station_result: print(live_station_result.model_dump_json(indent=2))

    await rapidapi_provider.shutdown()

if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
