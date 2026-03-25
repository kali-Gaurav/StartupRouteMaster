import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.services.rapidapi_provider import RapidApiProvider
from backend.schemas.rapidapi_models import TrainSchedule, TrainsBetweenStations, SeatAvailability, LiveStatus, PNRStatus

@pytest.fixture
def provider():
    return RapidApiProvider()

@pytest.mark.asyncio
async def test_get_train_schedule_success(provider: RapidApiProvider):
    mock_response = {
        "status": True,
        "data": {
            "trainNumber": "12345",
            "trainName": "Test Express",
            "runsOn": [{"dayCode": "MON", "runs": True}],
            "data": [
                {
                    "stationName": "Station A",
                    "stationCode": "STA",
                    "routeNumber": 1,
                    "arrivalTime": "10:00",
                    "departureTime": "10:05",
                    "dayOfJourney": 1,
                    "distance": "0",
                }
            ]
        }
    }
    
    provider._make_request = AsyncMock(return_value=mock_response)
    
    schedule = await provider.get_train_schedule("12345")
    
    assert schedule is not None
    assert isinstance(schedule, TrainSchedule)
    assert schedule.train_number == "12345"
    assert schedule.stops[0].station_code == "STA"

@pytest.mark.asyncio
async def test_get_train_schedule_api_failure(provider: RapidApiProvider):
    provider._make_request = AsyncMock(return_value=None)
    
    schedule = await provider.get_train_schedule("12345")
    
    assert schedule is None

    
    assert schedule is None

@pytest.mark.asyncio
async def test_get_trains_between_stations_success(provider: RapidApiProvider):
    mock_response = {
        "status": True,
        "data": [
            {
                "train_name": "Test Express",
                "train_number": "12345",
                "source_station_name": "Station A",
                "source_station_code": "STA",
                "destination_station_name": "Station B",
                "destination_station_code": "STB",
                "arrival_time": "12:00",
                "departure_time": "10:00",
                "duration": "2:00",
            }
        ]
    }
    
    provider._make_request = AsyncMock(return_value=mock_response)
    
    trains = await provider.get_trains_between_stations("STA", "STB")
    
    assert trains is not None
    assert isinstance(trains, TrainsBetweenStations)
    assert trains.trains[0].train_number == "12345"

@pytest.mark.asyncio
async def test_check_seat_availability_success(provider: RapidApiProvider):
    mock_response = {
        "status": True,
        "trainNumber": "12345",
        "trainName": "Test Express",
        "quota": "GN",
        "data": [
            {
                "date": "2026-03-23",
                "availabilityStatus": "AVAILABLE",
                "totalFare": 1000,
            }
        ]
    }
    
    provider._make_request = AsyncMock(return_value=mock_response)
    
    availability = await provider.check_seat_availability("12345", "SL", "GN", "STA", "STB", "2026-03-23")
    
    assert availability is not None
    assert isinstance(availability, SeatAvailability)
    assert availability.train_number == "12345"
    assert availability.availability[0].availability_status == "AVAILABLE"

@pytest.mark.asyncio
async def test_get_train_live_status_success(provider: RapidApiProvider):
    mock_response = {
        "status": True,
        "data": {
            "train_number": "12345",
            "current_station_name": "Station A",
            "current_station_code": "STA",
            "at_station": True,
            "distance_from_source": 0,
            "delay": 0,
            "status": "On Time",
            "last_updated": "2026-03-22T20:00:00",
        }
    }
    
    provider._make_request = AsyncMock(return_value=mock_response)
    
    live_status = await provider.get_train_live_status("12345")
    
    assert live_status is not None
    assert isinstance(live_status, LiveStatus)
    assert live_status.train_number == "12345"
    assert live_status.status == "On Time"

@pytest.mark.asyncio
async def test_get_pnr_status_success(provider: RapidApiProvider):
    mock_response = {
        "status": True,
        "data": {
            "pnrNumber": "1234567890",
            "trainNumber": "12345",
            "trainName": "Test Express",
            "fromStation": "STA",
            "toStation": "STB",
            "boardingPoint": "STA",
            "destinationStation": "STB",
            "journeyDate": "2026-03-23",
            "class": "SL",
            "passenger": [
                {
                    "number": 1,
                    "bookingStatus": "CNF",
                    "currentStatus": "CNF",
                }
            ],
            "chartPrepared": False,
        }
    }
    
    provider._make_request = AsyncMock(return_value=mock_response)
    
    pnr_status = await provider.get_pnr_status("1234567890")
    
    assert pnr_status is not None
    assert isinstance(pnr_status, PNRStatus)
    assert pnr_status.pnr_number == "1234567890"
    assert pnr_status.passengers[0].booking_status == "CNF"
