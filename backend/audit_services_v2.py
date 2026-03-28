import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock dependencies before imports if necessary
# For now, let's try direct imports and mock within tests

async def test_rapidapi_provider():
    logger.info("Testing RapidAPI Provider...")
    from services.rapidapi_provider import RapidApiProvider
    from schemas.rapidapi_models import SearchStation, SearchTrain
    
    provider = RapidApiProvider()
    from core.providers import ServiceStatus
    provider.status = ServiceStatus.HEALTHY
    provider.http_session = AsyncMock()
    provider.http_session.closed = False
    
    # Mock _execute_request to simulate API response
    with patch.object(RapidApiProvider, '_execute_request', new_callable=AsyncMock) as mock_exec:
        # Test search_station
        mock_exec.return_value = {
            "status": True,
            "message": "Success",
            "timestamp": 123456789,
            "data": [
                {"stationName": "New Delhi", "stationCode": "NDLS"},
                {"stationName": "Mumbai Central", "stationCode": "MMCT"}
            ]
        }
        
        res = await provider.search_station("Delhi")
        assert res is not None
        assert len(res.stations) == 2
        # SearchStationResult uses station_code
        assert res.stations[0].station_code == "NDLS"
        logger.info("✅ RapidAPI search_station test passed.")

        # Test fallback/mock behavior if API fails
        mock_exec.return_value = None
        res = await provider.search_station("Mumbai")
        assert res is None
        logger.info("✅ RapidAPI failure handling test passed.")

async def test_station_search():
    logger.info("Testing Station Search Service...")
    from services.station_search_service import StationSearchEngine, StationSuggestion
    
    # Mock DB loading to avoid needing the actual SQLite file for this test
    with patch.object(StationSearchEngine, '_load_from_db') as mock_load:
        engine = StationSearchEngine()
        engine._initialized = True
        engine._stations = [
            StationSuggestion(id=1, code="NDLS", name="NEW DELHI", city="DELHI", popularity=100.0),
            StationSuggestion(id=2, code="MMCT", name="MUMBAI CENTRAL", city="MUMBAI", popularity=90.0),
            StationSuggestion(id=3, code="SBC", name="KSR BENGALURU", city="BENGALURU", popularity=80.0),
        ]
        engine._station_map = {
            "NDLS": engine._stations[0],
            "MMCT": engine._stations[1],
            "SBC": engine._stations[2],
            "1": engine._stations[0],
            "2": engine._stations[1],
            "3": engine._stations[2],
        }
        engine._name_to_code = {
            "new delhi": "NDLS",
            "mumbai central": "MMCT",
            "ksr bengaluru": "SBC"
        }
        
        # Test fuzzy match
        res = engine.suggest("Dilli")
        assert len(res) > 0
        assert res[0].code == "NDLS"
        logger.info("✅ Station Search fuzzy match (alias) test passed.")
        
        res = engine.suggest("Mmbai")
        assert len(res) > 0
        assert res[0].code == "MMCT"
        logger.info("✅ Station Search fuzzy match (typo) test passed.")

async def test_telegram_services():
    logger.info("Testing Telegram Services...")
    from services.telegram_service import telegram_service
    from services.telegram_dispatcher import telegram_dispatcher
    
    # Mock httpx.AsyncClient
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        
        # Test telegram_service
        success = await telegram_service.send_message("12345", "Hello")
        # If token is missing, it should return False and log warning
        if not os.getenv("TELEGRAM_TOKEN"):
             assert success is False
             logger.info("✅ Telegram Service handled missing token correctly.")
        else:
             assert success is True
             logger.info("✅ Telegram Service sent message successfully.")

    # Check for the 'os' import bug in telegram_dispatcher
    try:
        from services.telegram_dispatcher import telegram_dispatcher
        # This shouldn't crash if imported correctly
        logger.info("✅ Telegram Dispatcher imported successfully.")
    except Exception as e:
        logger.error(f"❌ Telegram Dispatcher import failed: {e}")

async def test_sos_logic():
    logger.info("Testing SOS/Emergency Logic...")
    from services.emergency.safety_service import SafetyService
    
    service = SafetyService()
    
    # Test haversine
    dist = service.haversine(28.6139, 77.2090, 19.0760, 72.8777) # Delhi to Mumbai
    assert 1100 < dist < 1200
    logger.info(f"✅ Haversine distance: {dist:.2f} km")

    # Mock DB session for deviation check
    with patch("services.emergency.safety_service.SessionTransit") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        # Mock user DB
        db_user = MagicMock()
        db_user.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        
        res = await service.check_journey_deviation("user123", 28.0, 77.0, db_user)
        assert res["status"] == "no_active_trip"
        logger.info("✅ SOS Deviation check (no trip) passed.")

async def test_chatbot_nlp():
    logger.info("Testing Chatbot NLP...")
    from services.nlp_parser import parse_passengers, map_intent_to_action
    
    text = "Gaurav (30), Anjali (28)"
    passengers = parse_passengers(text)
    assert len(passengers) == 2
    assert passengers[0]["fullName"] == "Gaurav"
    assert passengers[0]["age"] == 30
    logger.info("✅ NLP Passenger parsing test passed.")
    
    intent = map_intent_to_action("I want to book a ticket for Gaurav (30)")
    assert intent["action"] == "book"
    assert len(intent["data"]) == 1
    logger.info("✅ NLP Intent mapping test passed.")

async def main():
    try:
        await test_rapidapi_provider()
        await test_station_search()
        await test_telegram_services()
        await test_sos_logic()
        await test_chatbot_nlp()
        logger.info("\n✨ ALL BACKEND SERVICE AUDITS PASSED!")
    except Exception as e:
        logger.error(f"\n❌ AUDIT FAILED: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
