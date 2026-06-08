"""
Unit Tests for Booking Routes API Structure

Tests the FastAPI application structure for the Booking API,
including APIRouter configuration, CORS settings, and dependency injection.

Requirements: REQ-028 (REST API Specification)
"""

import pytest
import sys
import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add backend to path
backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


class TestBookingRouterStructure:
    """Test the structure and configuration of the booking router."""

    def test_router_import(self):
        """Test that the booking router can be imported successfully."""
        try:
            from api.booking_routes import router
            assert router is not None
        except ImportError as e:
            pytest.fail(f"Failed to import booking router: {e}")

    def test_router_prefix(self):
        """Test that the router has the correct prefix."""
        from api.booking_routes import router
        assert router.prefix == "/api/v1/bookings"

    def test_router_tags(self):
        """Test that the router has the correct tags."""
        from api.booking_routes import router
        assert "bookings" in router.tags

    def test_router_has_create_endpoint(self):
        """Test that the router has a POST endpoint for creating bookings."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        # Routes include the prefix, so check for full path
        assert "/api/v1/bookings/" in route_paths

    def test_router_has_get_by_id_endpoint(self):
        """Test that the router has a GET endpoint for fetching booking by ID."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        assert "/api/v1/bookings/{booking_id}" in route_paths

    def test_router_has_pnr_lookup_endpoint(self):
        """Test that the router has a GET endpoint for PNR lookup."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        assert "/api/v1/bookings/pnr/{pnr_number}" in route_paths

    def test_router_has_list_endpoint(self):
        """Test that the router has a GET endpoint for listing bookings."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        # The list endpoint is at "/" (same as create but with GET)
        assert "/api/v1/bookings/" in route_paths

    def test_router_has_cancel_endpoint(self):
        """Test that the router has a POST endpoint for cancelling bookings."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        assert "/api/v1/bookings/{booking_id}/cancel" in route_paths

    def test_router_has_health_endpoint(self):
        """Test that the router has a health check endpoint."""
        from api.booking_routes import router
        route_paths = [getattr(route, "path", None) for route in router.routes]
        assert "/api/v1/bookings/health" in route_paths


class TestBookingSchemas:
    """Test the booking request and response schemas."""

    def test_booking_request_schema_import(self):
        """Test that BookingRequestSchema can be imported."""
        try:
            from schemas.base import BookingRequestSchema
            assert BookingRequestSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BookingRequestSchema: {e}")

    def test_booking_response_schema_import(self):
        """Test that BookingResponseSchema can be imported."""
        try:
            from schemas.base import BookingResponseSchema
            assert BookingResponseSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BookingResponseSchema: {e}")

    def test_booking_response_state_fields(self):
        """Test that BookingResponseSchema accepts state metadata."""
        from schemas.base import BookingResponseSchema

        response = BookingResponseSchema(
            id="1",
            user_id="user_1",
            pnr_number="PNR123",
            travel_date=date.today(),
            booking_status="pending",
            train_details=None,
            passengers=[],
            total_amount=100.0,
            amount_paid=100.0,
            payment_url=None,
            payment_status="created",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow(),
            current_state={"booking_status": "pending", "escrow_status": "created"},
            valid_next_actions=["cancel", "submit_utr"],
            state_transition_history=[
                {
                    "audit_id": "audit_1",
                    "action": "created",
                    "previous_state": None,
                    "new_state": "pending",
                    "actor_type": "user",
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )
        assert response.current_state is not None
        assert response.current_state["booking_status"] == "pending"
        assert response.valid_next_actions is not None
        assert "cancel" in response.valid_next_actions
        assert response.state_transition_history is not None
        assert response.state_transition_history[0]["action"] == "created"

    def test_v2_booking_response_schema_state_fields(self):
        """Test that the v2 BookingResponseSchema accepts state and audit metadata."""
        from schemas.booking import BookingResponseSchema

        response = BookingResponseSchema(
            id="2",
            user_id="user_2",
            pnr_number="PNR456",
            booking_status="confirmed",
            escrow_status="COMPLETED",
            amount_paid=1500.0,
            is_tatkal=False,
            priority=10,
            service_type="UNLOCK",
            is_unlocked=True,
            created_at=datetime.utcnow(),
            current_state={"booking_status": "confirmed", "escrow_status": "COMPLETED"},
            valid_next_actions=["cancel"],
            audit_trail=[
                {
                    "audit_id": "audit_2",
                    "action": "confirmed",
                    "previous_state": "pending",
                    "new_state": "confirmed",
                    "actor_type": "SYSTEM",
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )
        assert response.current_state["booking_status"] == "confirmed"
        assert response.valid_next_actions == ["cancel"]
        assert response.audit_trail is not None
        assert response.audit_trail[0]["action"] == "confirmed"

    def test_pnr_lookup_schema_import(self):
        """Test that PNRLookupResponseSchema can be imported."""
        try:
            from schemas.base import PNRLookupResponseSchema
            assert PNRLookupResponseSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import PNRLookupResponseSchema: {e}")

    def test_booking_list_schema_import(self):
        """Test that BookingListResponseSchema can be imported."""
        try:
            from schemas.base import BookingListResponseSchema
            assert BookingListResponseSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BookingListResponseSchema: {e}")

    def test_cancellation_schema_import(self):
        """Test that BookingCancellationSchema can be imported."""
        try:
            from schemas.base import BookingCancellationSchema
            assert BookingCancellationSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import BookingCancellationSchema: {e}")

    def test_error_response_schema_import(self):
        """Test that ErrorResponseSchema can be imported."""
        try:
            from schemas.base import ErrorResponseSchema
            assert ErrorResponseSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import ErrorResponseSchema: {e}")

    def test_passenger_schema_import(self):
        """Test that PassengerSchema can be imported."""
        try:
            from schemas.base import PassengerSchema
            assert PassengerSchema is not None
        except ImportError as e:
            pytest.fail(f"Failed to import PassengerSchema: {e}")

    def test_booking_request_validation(self):
        """Test that BookingRequestSchema validates correctly."""
        from schemas.base import BookingRequestSchema
        from pydantic import ValidationError
        
        # Valid request
        valid_data = {
            "journey_id": "journey_123",
            "travel_date": date.today(),
            "passengers": [
                {
                    "full_name": "John Doe",
                    "age": 35,
                    "gender": "M"
                }
            ],
            "class_type": "3A",
            "payment_method": "UPI"
        }
        request = BookingRequestSchema(**valid_data)
        assert request.journey_id == "journey_123"
        assert len(request.passengers) == 1

    def test_booking_request_invalid_gender(self):
        """Test that BookingRequestSchema rejects invalid gender."""
        from schemas.base import BookingRequestSchema
        from pydantic import ValidationError
        
        invalid_data = {
            "journey_id": "journey_123",
            "travel_date": date.today(),
            "passengers": [
                {
                    "full_name": "John Doe",
                    "age": 35,
                    "gender": "X"  # Invalid gender
                }
            ],
            "class_type": "3A",
            "payment_method": "UPI"
        }
        with pytest.raises(ValidationError):
            BookingRequestSchema(**invalid_data)

    def test_booking_request_invalid_class_type(self):
        """Test that BookingRequestSchema rejects invalid class type."""
        from schemas.base import BookingRequestSchema
        from pydantic import ValidationError
        
        invalid_data = {
            "journey_id": "journey_123",
            "travel_date": date.today(),
            "passengers": [
                {
                    "full_name": "John Doe",
                    "age": 35,
                    "gender": "M"
                }
            ],
            "class_type": "INVALID_CLASS",  # Invalid class
            "payment_method": "UPI"
        }
        with pytest.raises(ValidationError):
            BookingRequestSchema(**invalid_data)

    def test_booking_request_invalid_payment_method(self):
        """Test that BookingRequestSchema rejects invalid payment method."""
        from schemas.base import BookingRequestSchema
        from pydantic import ValidationError
        
        invalid_data = {
            "journey_id": "journey_123",
            "travel_date": date.today(),
            "passengers": [
                {
                    "full_name": "John Doe",
                    "age": 35,
                    "gender": "M"
                }
            ],
            "class_type": "3A",
            "payment_method": "CASH"  # Invalid payment method
        }
        with pytest.raises(ValidationError):
            BookingRequestSchema(**invalid_data)


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    def test_cors_origins_defined(self):
        """Test that CORS origins are defined."""
        from api.booking_routes import CORS_ORIGINS
        assert isinstance(CORS_ORIGINS, list)
        assert len(CORS_ORIGINS) > 0
        assert "http://localhost:3000" in CORS_ORIGINS

    def test_cors_setup_function_exists(self):
        """Test that CORS setup function exists."""
        from api.booking_routes import setup_cors_middleware
        assert callable(setup_cors_middleware)


class TestDependencyInjection:
    """Test dependency injection setup for services."""

    def test_booking_service_factory(self):
        """Test that booking service factory exists and is callable."""
        from api.booking_routes import get_booking_service
        assert callable(get_booking_service)

    def test_fraud_detection_service_factory(self):
        """Test that fraud detection service factory exists and is callable."""
        from api.booking_routes import get_fraud_detection_service
        assert callable(get_fraud_detection_service)

    def test_payment_service_factory(self):
        """Test that payment service factory exists and is callable."""
        from api.booking_routes import get_payment_service
        assert callable(get_payment_service)

    def test_notification_service_factory(self):
        """Test that notification service factory exists and is callable."""
        from api.booking_routes import get_notification_service
        assert callable(get_notification_service)


class TestErrorResponses:
    """Test error response schemas and handling."""

    def test_error_response_schema(self):
        """Test ErrorResponseSchema creates valid error responses."""
        from schemas.base import ErrorResponseSchema
        
        error = ErrorResponseSchema(
            detail="Booking not found",
            error_code="ERR005"
        )
        assert error.detail == "Booking not found"
        assert error.error_code == "ERR005"
        assert isinstance(error.timestamp, datetime)

    def test_error_response_schema_default_timestamp(self):
        """Test ErrorResponseSchema has default timestamp."""
        from schemas.base import ErrorResponseSchema
        
        error = ErrorResponseSchema(detail="Test error")
        assert error.timestamp is not None


class TestBookingCancellationSchema:
    """Test booking cancellation schema."""

    def test_cancellation_schema_with_reason(self):
        """Test cancellation schema with reason."""
        from schemas.base import BookingCancellationSchema
        
        cancellation = BookingCancellationSchema(reason="Changed travel plans")
        assert cancellation.reason == "Changed travel plans"

    def test_cancellation_schema_without_reason(self):
        """Test cancellation schema without reason."""
        from schemas.base import BookingCancellationSchema
        
        cancellation = BookingCancellationSchema(reason=None)
        assert cancellation.reason is None


class TestPNRLookupSchema:
    """Test PNR lookup response schema."""

    def test_pnr_lookup_response_schema(self):
        """Test PNRLookupResponseSchema creates valid responses."""
        from schemas.base import PNRLookupResponseSchema
        
        response = PNRLookupResponseSchema(
            pnr_number="1234567890",
            train_number="12951",
            train_name="Rajdhani Express",
            travel_date=date.today(),
            booking_status="confirmed",
            passenger_count=2,
            class_type="3A"
        )
        assert response.pnr_number == "1234567890"

    def test_pnr_lookup_state_fields(self):
        """Test PNRLookupResponseSchema accepts state metadata."""
        from schemas.base import PNRLookupResponseSchema

        response = PNRLookupResponseSchema(
            pnr_number="1234567890",
            train_number="12951",
            train_name="Rajdhani Express",
            travel_date=date.today(),
            booking_status="confirmed",
            passenger_count=2,
            class_type="3A",
            current_state={"booking_status": "confirmed", "escrow_status": "completed"},
            valid_next_actions=["cancel"],
        )
        assert response.current_state is not None
        assert response.current_state["escrow_status"] == "completed"
        assert response.valid_next_actions == ["cancel"]
        assert response.passenger_count == 2


class TestTrainInfoSchema:
    """Test train info schema."""

    def test_train_info_schema(self):
        """Test TrainInfoSchema creates valid responses."""
        from schemas.base import TrainInfoSchema
        
        train_info = TrainInfoSchema(
            train_number="12951",
            train_name="Rajdhani Express",
            from_station="NDLS",
            to_station="MMCT",
            departure_time="16:00",
            arrival_time="08:00",
            duration_minutes=960
        )
        assert train_info.train_number == "12951"
        assert train_info.duration_minutes == 960


class TestPassengerSchema:
    """Test passenger schema."""

    def test_passenger_schema(self):
        """Test PassengerSchema creates valid passenger info."""
        from schemas.base import PassengerSchema
        
        passenger = PassengerSchema(
            full_name="John Doe",
            age=35,
            gender="M",
            phone_number="+919876543210",
            berth_preference="LOWER"
        )
        assert passenger.full_name == "John Doe"
        assert passenger.age == 35
        assert passenger.gender == "M"

    def test_passenger_schema_optional_fields(self):
        """Test PassengerSchema with optional fields."""
        from schemas.base import PassengerSchema
        
        passenger = PassengerSchema(
            full_name="Jane Doe",
            age=30,
            gender="F"
        )
        assert passenger.berth_preference is None
        assert passenger.meal_preference is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
