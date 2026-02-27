"""
Test Route Verification Service
Tests for route verification during unlock payment flow.
"""

import pytest
import asyncio
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from services.route_verification_service import RouteVerificationService
from database.models import Trip, Stop, StopTime, Route, Segment, Station


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def verification_service(mock_db):
    """Create RouteVerificationService instance."""
    return RouteVerificationService(mock_db)


@pytest.mark.asyncio
async def test_verify_route_with_direct_params(verification_service, mock_db):
    """Test verification with direct parameters (fastest path)."""
    # Mock DataProvider
    with patch.object(verification_service.data_provider, 'verify_seat_availability_unified') as mock_seat, \
         patch.object(verification_service.data_provider, 'verify_fare_unified') as mock_fare:
        
        # Mock responses
        mock_seat.return_value = {
            "status": "verified",
            "available_seats": 10,
            "total_seats": 64,
            "source": "rapidapi"
        }
        mock_fare.return_value = {
            "status": "verified",
            "total_fare": 1200.0,
            "source": "rapidapi"
        }
        
        # Mock station lookup
        mock_from_stop = Mock(spec=Stop)
        mock_from_stop.code = "NDLS"
        mock_from_stop.name = "New Delhi"
        mock_to_stop = Mock(spec=Stop)
        mock_to_stop.code = "MMCT"
        mock_to_stop.name = "Mumbai Central"
        
        # Mock Station
        mock_station = Mock(spec=Station)
        mock_station.id = "uuid-station"
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_from_stop,  # from_stop code lookup
            mock_to_stop,    # to_stop code lookup
            mock_station,    # from_station name lookup
            mock_station,    # to_station name lookup
            None,            # segment
        ]
        
        result = await verification_service.verify_route_for_unlock(
            route_id="test_route",
            travel_date="2026-03-15",
            train_number="12951",
            from_station_code="NDLS",
            to_station_code="MMCT"
        )
        
        assert result["success"] is True
        assert result["route_info"]["train_number"] == "12951"
        assert result["route_info"]["from_station_code"] == "NDLS"
        assert result["route_info"]["to_station_code"] == "MMCT"
        assert "sl_availability" in result["verification"]
        assert "ac3_availability" in result["verification"]
        assert "sl_fare" in result["verification"]
        assert "ac3_fare" in result["verification"]
        assert result["api_calls_made"] == 4  # 4 RapidAPI calls


@pytest.mark.asyncio
async def test_verify_route_with_journey_id(verification_service, mock_db):
    """Test verification with journey_id format."""
    # Mock Trip
    mock_trip = Mock(spec=Trip)
    mock_trip.id = 12345
    mock_trip.trip_id = "12951_20260315_NDLS-MMCT"
    
    # Mock Route
    mock_route = Mock(spec=Route)
    mock_route.short_name = "12951"
    mock_route.route_id = "12951"
    mock_trip.route = mock_route
    
    # Mock StopTimes
    mock_stop_time1 = Mock(spec=StopTime)
    mock_stop_time1.stop_id = 1
    mock_stop_time1.stop_sequence = 0
    mock_stop_time2 = Mock(spec=StopTime)
    mock_stop_time2.stop_id = 2
    mock_stop_time2.stop_sequence = 10
    
    # Mock Stops
    mock_from_stop = Mock(spec=Stop)
    mock_from_stop.id = 1
    mock_from_stop.code = "NDLS"
    mock_from_stop.name = "New Delhi"
    mock_to_stop = Mock(spec=Stop)
    mock_to_stop.id = 2
    mock_to_stop.code = "MMCT"
    mock_to_stop.name = "Mumbai Central"
    
    # Mock Segment
    mock_segment = Mock(spec=Segment)
    mock_segment.id = "seg_123"
    
    # Setup query chain
    mock_stop_query = Mock()
    mock_stop_query.filter.return_value.first.side_effect = [mock_from_stop, mock_to_stop]
    
    def query_side_effect(model):
        if model == Trip:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_trip
            return mock_query
        elif model == StopTime:
            mock_query = Mock()
            mock_query.filter.return_value.order_by.return_value.all.return_value = [mock_stop_time1, mock_stop_time2]
            return mock_query
        elif model == Stop:
            return mock_stop_query
        elif model == Segment:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_segment
            return mock_query
        elif model == Station:
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = Mock(id="uuid-123")
            return mock_query
        return Mock()
    
    mock_db.query.side_effect = query_side_effect
    
    # Mock DataProvider
    with patch.object(verification_service.data_provider, 'verify_seat_availability_unified') as mock_seat, \
         patch.object(verification_service.data_provider, 'verify_fare_unified') as mock_fare:
        
        mock_seat.return_value = {"status": "verified", "source": "rapidapi"}
        mock_fare.return_value = {"status": "verified", "source": "rapidapi"}
        
        result = await verification_service.verify_route_for_unlock(
            route_id="rt_12345_1234567890",
            travel_date="2026-03-15"
        )
        
        assert result["success"] is True
        assert result["route_info"]["train_number"] == "12951"
        assert result["route_info"]["from_station_code"] == "NDLS"
        assert result["route_info"]["to_station_code"] == "MMCT"


@pytest.mark.asyncio
async def test_verify_route_database_fallback(verification_service, mock_db):
    """Test verification falls back to database when RapidAPI unavailable."""
    # Mock DataProvider to return database fallback
    with patch.object(verification_service.data_provider, 'verify_seat_availability_unified') as mock_seat, \
         patch.object(verification_service.data_provider, 'verify_fare_unified') as mock_fare:
        
        mock_seat.return_value = {
            "status": "verified",
            "available_seats": 5,
            "total_seats": 64,
            "booked_seats": 59,
            "message": "Verified",
            "source": "database"  # Database fallback
        }
        mock_fare.return_value = {
            "status": "verified",
            "total_fare": 1000.0,
            "base_fare": 950.0,
            "GST": 50.0,
            "message": "Verified",
            "source": "database"  # Database fallback
        }
        
        # Mock station lookup
        mock_from_stop = Mock(spec=Stop)
        mock_from_stop.code = "NDLS"
        mock_from_stop.name = "New Delhi"
        mock_from_stop.id = 1
        mock_to_stop = Mock(spec=Stop)
        mock_to_stop.code = "MMCT"
        mock_to_stop.name = "Mumbai Central"
        mock_to_stop.id = 2
        
        # Mock Station
        mock_station = Mock(spec=Station)
        mock_station.id = "uuid-station"

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_from_stop, # code lookup
            mock_to_stop,   # code lookup
            mock_station,   # from_station name lookup
            mock_station,   # to_station name lookup
            None,           # segment
        ]
        
        result = await verification_service.verify_route_for_unlock(
            route_id="test_route",
            travel_date="2026-03-15",
            train_number="12951",
            from_station_code="NDLS",
            to_station_code="MMCT"
        )
        
        assert result["success"] is True
        assert result["api_calls_made"] == 0  # No RapidAPI calls
        assert result["verification"]["sl_availability"]["source"] == "database"


@pytest.mark.asyncio
async def test_verify_route_missing_info(verification_service, mock_db):
    """Test verification with missing route information."""
    result = await verification_service.verify_route_for_unlock(
        route_id="invalid_route",
        travel_date="2026-03-15"
    )
    
    # Should still succeed but with warnings
    assert "warnings" in result or result.get("success") is False
    # Should use database fallback


@pytest.mark.asyncio
async def test_verify_route_invalid_date(verification_service, mock_db):
    """Test verification with invalid date format."""
    result = await verification_service.verify_route_for_unlock(
        route_id="test_route",
        travel_date="invalid-date",
        train_number="12951",
        from_station_code="NDLS",
        to_station_code="MMCT"
    )
    
    assert result["success"] is False
    assert "error" in result
    assert "Invalid travel date" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
