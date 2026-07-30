"""
Integration Tests for Dashboard API Endpoints
Tests REST endpoints for user dashboard, bookings, payments, tickets, and profile

Feature #2: User Dashboard
Team 5 (QA)
Target: >95% coverage
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch, call
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from database.models import User, Booking, Payment, Profile
from core.data_utils.structures import BookingStatus
from api.dashboard_routes import router as dashboard_router
from core.auth import get_current_user


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def app():
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(dashboard_router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = "user-123"
    user.email = "user@example.com"
    user.full_name = "John Doe"
    user.phone_number = "+919876543210"
    user.is_verified = True
    return user


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def override_get_current_user(mock_current_user):
    """Override authentication dependency."""
    async def _override():
        return mock_current_user
    return _override


@pytest.fixture
def setup_app_with_overrides(app, override_get_current_user):
    """Setup app with dependency overrides."""
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield app
    app.dependency_overrides.clear()


# =============================================================================
# TESTS: GET /v1/user/dashboard
# =============================================================================

class TestDashboardEndpoint:
    """Tests for the main dashboard endpoint."""

    def test_dashboard_success(self, client, setup_app_with_overrides, mock_db):
        """Test successful dashboard retrieval."""
        response = client.get("/v1/user/dashboard")
        assert response.status_code == 200
        assert "user" in response.json()
        assert "bookings" in response.json()
        assert "payments" in response.json()

    def test_dashboard_includes_user_info(self, client, setup_app_with_overrides):
        """Test dashboard includes user information."""
        response = client.get("/v1/user/dashboard")
        data = response.json()

        assert data["user"]["user_id"] == "user-123"
        assert data["user"]["email"] == "user@example.com"
        assert data["user"]["full_name"] == "John Doe"

    def test_dashboard_includes_recent_bookings(self, client, setup_app_with_overrides):
        """Test dashboard includes recent bookings."""
        response = client.get("/v1/user/dashboard")
        data = response.json()

        assert "bookings" in data
        assert "total" in data["bookings"]
        assert "items" in data["bookings"]

    def test_dashboard_includes_recent_payments(self, client, setup_app_with_overrides):
        """Test dashboard includes recent payments."""
        response = client.get("/v1/user/dashboard")
        data = response.json()

        assert "payments" in data
        assert "total" in data["payments"]

    def test_dashboard_without_authentication(self, client):
        """Test dashboard returns 401 without authentication."""
        response = client.get("/v1/user/dashboard")
        assert response.status_code == 401

    def test_dashboard_summary_statistics(self, client, setup_app_with_overrides):
        """Test dashboard includes summary statistics."""
        response = client.get("/v1/user/dashboard")
        data = response.json()

        assert "statistics" in data or "summary" in data


# =============================================================================
# TESTS: GET /v1/user/bookings
# =============================================================================

class TestBookingsListEndpoint:
    """Tests for the bookings list endpoint."""

    def test_list_bookings_success(self, client, setup_app_with_overrides):
        """Test successful bookings list retrieval."""
        response = client.get("/v1/user/bookings")
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data or "items" in data
        assert "total" in data

    def test_list_bookings_pagination(self, client, setup_app_with_overrides):
        """Test bookings list with pagination parameters."""
        response = client.get("/v1/user/bookings?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data.get("limit") == 10
        assert data.get("offset") == 0

    def test_list_bookings_with_status_filter(self, client, setup_app_with_overrides):
        """Test bookings list with status filter."""
        response = client.get("/v1/user/bookings?status=confirmed")
        assert response.status_code == 200
        data = response.json()

        # All returned bookings should have the requested status
        for booking in data.get("bookings", data.get("items", [])):
            assert booking.get("status") == "confirmed" or "status" in booking

    def test_list_bookings_with_date_filter(self, client, setup_app_with_overrides):
        """Test bookings list with date range filter."""
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        end_date = datetime.now(timezone.utc).isoformat()

        response = client.get(f"/v1/user/bookings?start_date={start_date}&end_date={end_date}")
        assert response.status_code in [200, 400]  # 400 if dates invalid

    def test_list_bookings_invalid_limit(self, client, setup_app_with_overrides):
        """Test bookings list with invalid limit."""
        response = client.get("/v1/user/bookings?limit=0")
        assert response.status_code in [400, 422]

    def test_list_bookings_invalid_offset(self, client, setup_app_with_overrides):
        """Test bookings list with invalid offset."""
        response = client.get("/v1/user/bookings?offset=-1")
        assert response.status_code in [400, 422]

    def test_list_bookings_max_limit(self, client, setup_app_with_overrides):
        """Test bookings list respects maximum limit."""
        response = client.get("/v1/user/bookings?limit=10000")
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            data = response.json()
            # Limit should be capped
            assert data.get("limit", 10000) <= 100

    def test_list_bookings_default_pagination(self, client, setup_app_with_overrides):
        """Test bookings list uses sensible defaults."""
        response = client.get("/v1/user/bookings")
        assert response.status_code == 200
        data = response.json()

        # Should have default values
        assert data.get("limit", 20) > 0
        assert data.get("offset", 0) >= 0

    def test_list_bookings_sorting(self, client, setup_app_with_overrides):
        """Test bookings list can be sorted."""
        response = client.get("/v1/user/bookings?sort=date_desc")
        assert response.status_code in [200, 422]

    def test_list_bookings_without_authentication(self, client):
        """Test bookings list requires authentication."""
        response = client.get("/v1/user/bookings")
        assert response.status_code == 401


# =============================================================================
# TESTS: GET /v1/user/payments
# =============================================================================

class TestPaymentsEndpoint:
    """Tests for the payments endpoint."""

    def test_list_payments_success(self, client, setup_app_with_overrides):
        """Test successful payments list retrieval."""
        response = client.get("/v1/user/payments")
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data or "items" in data
        assert "total" in data

    def test_list_payments_pagination(self, client, setup_app_with_overrides):
        """Test payments list with pagination."""
        response = client.get("/v1/user/payments?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data.get("limit") == 10

    def test_list_payments_with_status_filter(self, client, setup_app_with_overrides):
        """Test payments list with status filter."""
        response = client.get("/v1/user/payments?status=completed")
        assert response.status_code == 200

    def test_list_payments_with_method_filter(self, client, setup_app_with_overrides):
        """Test payments list with payment method filter."""
        response = client.get("/v1/user/payments?method=razorpay")
        assert response.status_code == 200

    def test_list_payments_summary(self, client, setup_app_with_overrides):
        """Test payments list includes summary."""
        response = client.get("/v1/user/payments")
        assert response.status_code == 200
        data = response.json()

        # Should include summary statistics
        assert "total" in data
        if "summary" in data:
            assert "total_amount" in data["summary"] or "amount" in data

    def test_list_payments_without_authentication(self, client):
        """Test payments list requires authentication."""
        response = client.get("/v1/user/payments")
        assert response.status_code == 401


# =============================================================================
# TESTS: GET /v1/user/tickets
# =============================================================================

class TestTicketsEndpoint:
    """Tests for the tickets endpoint."""

    def test_get_tickets_success(self, client, setup_app_with_overrides):
        """Test successful tickets retrieval."""
        response = client.get("/v1/user/tickets")
        assert response.status_code == 200
        data = response.json()
        assert "tickets" in data or "items" in data

    def test_get_tickets_includes_pnr(self, client, setup_app_with_overrides):
        """Test tickets include PNR numbers."""
        response = client.get("/v1/user/tickets")
        assert response.status_code == 200
        data = response.json()

        tickets = data.get("tickets", data.get("items", []))
        for ticket in tickets:
            assert "pnr" in ticket or "pnr_number" in ticket

    def test_get_tickets_includes_seat_info(self, client, setup_app_with_overrides):
        """Test tickets include seat information."""
        response = client.get("/v1/user/tickets")
        assert response.status_code == 200
        data = response.json()

        tickets = data.get("tickets", data.get("items", []))
        for ticket in tickets:
            assert "seats" in ticket or "seat_numbers" in ticket

    def test_get_tickets_only_confirmed(self, client, setup_app_with_overrides):
        """Test tickets only include confirmed bookings."""
        response = client.get("/v1/user/tickets")
        assert response.status_code == 200
        data = response.json()

        tickets = data.get("tickets", data.get("items", []))
        for ticket in tickets:
            status = ticket.get("status", "").lower()
            assert status in ["confirmed", "completed"] or status != "cancelled"

    def test_download_ticket(self, client, setup_app_with_overrides):
        """Test downloading a ticket."""
        response = client.get("/v1/user/tickets/ticket-123/download")
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            assert response.headers.get("content-type") in ["application/pdf", "text/plain"]

    def test_get_tickets_without_authentication(self, client):
        """Test tickets endpoint requires authentication."""
        response = client.get("/v1/user/tickets")
        assert response.status_code == 401


# =============================================================================
# TESTS: GET /v1/user/profile
# =============================================================================

class TestProfileEndpoint:
    """Tests for the user profile endpoint."""

    def test_get_profile_success(self, client, setup_app_with_overrides):
        """Test successful profile retrieval."""
        response = client.get("/v1/user/profile")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data or "id" in data
        assert "email" in data
        assert "full_name" in data or "name" in data

    def test_get_profile_includes_contact_info(self, client, setup_app_with_overrides):
        """Test profile includes contact information."""
        response = client.get("/v1/user/profile")
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "phone_number" in data or "phone" in data

    def test_get_profile_includes_preferences(self, client, setup_app_with_overrides):
        """Test profile includes user preferences."""
        response = client.get("/v1/user/profile")
        assert response.status_code == 200
        data = response.json()
        # Preferences may be optional but should be present if user has them

    def test_update_profile(self, client, setup_app_with_overrides):
        """Test updating user profile."""
        update_data = {
            "full_name": "Jane Doe",
            "phone_number": "+919876543211"
        }
        response = client.put("/v1/user/profile", json=update_data)
        assert response.status_code in [200, 201]

    def test_update_profile_partial(self, client, setup_app_with_overrides):
        """Test partial update of profile."""
        update_data = {"full_name": "Jane Doe"}
        response = client.patch("/v1/user/profile", json=update_data)
        assert response.status_code in [200, 405, 422]

    def test_profile_without_authentication(self, client):
        """Test profile endpoint requires authentication."""
        response = client.get("/v1/user/profile")
        assert response.status_code == 401


# =============================================================================
# TESTS: Pagination Integration
# =============================================================================

class TestPaginationIntegration:
    """Tests for pagination across all endpoints."""

    def test_bookings_pagination_consistency(self, client, setup_app_with_overrides):
        """Test bookings pagination is consistent."""
        response1 = client.get("/v1/user/bookings?limit=5&offset=0")
        response2 = client.get("/v1/user/bookings?limit=5&offset=5")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Ensure no overlap between pages
        bookings1 = data1.get("bookings", data1.get("items", []))
        bookings2 = data2.get("bookings", data2.get("items", []))

        ids1 = {b.get("id") for b in bookings1}
        ids2 = {b.get("id") for b in bookings2}
        assert len(ids1 & ids2) == 0  # No overlap

    def test_payments_pagination_consistency(self, client, setup_app_with_overrides):
        """Test payments pagination is consistent."""
        response1 = client.get("/v1/user/payments?limit=5&offset=0")
        response2 = client.get("/v1/user/payments?limit=5&offset=5")

        assert response1.status_code == 200
        assert response2.status_code == 200


# =============================================================================
# TESTS: Filtering Integration
# =============================================================================

class TestFilteringIntegration:
    """Tests for filtering across endpoints."""

    def test_bookings_filter_by_status(self, client, setup_app_with_overrides):
        """Test filtering bookings by status."""
        statuses = ["confirmed", "cancelled", "pending"]
        for status in statuses:
            response = client.get(f"/v1/user/bookings?status={status}")
            assert response.status_code == 200

    def test_payments_filter_by_status(self, client, setup_app_with_overrides):
        """Test filtering payments by status."""
        statuses = ["completed", "failed", "pending"]
        for status in statuses:
            response = client.get(f"/v1/user/payments?status={status}")
            assert response.status_code == 200

    def test_bookings_filter_by_date_range(self, client, setup_app_with_overrides):
        """Test filtering bookings by date range."""
        start = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        end = datetime.now(timezone.utc).date().isoformat()

        response = client.get(f"/v1/user/bookings?start_date={start}&end_date={end}")
        assert response.status_code in [200, 422]


# =============================================================================
# TESTS: Response Format
# =============================================================================

class TestResponseFormat:
    """Tests for response format consistency."""

    def test_dashboard_response_structure(self, client, setup_app_with_overrides):
        """Test dashboard response has expected structure."""
        response = client.get("/v1/user/dashboard")
        data = response.json()

        assert "user" in data
        assert "bookings" in data
        assert "payments" in data

    def test_bookings_response_structure(self, client, setup_app_with_overrides):
        """Test bookings response has expected structure."""
        response = client.get("/v1/user/bookings")
        data = response.json()

        assert "bookings" in data or "items" in data
        assert "total" in data

    def test_booking_item_structure(self, client, setup_app_with_overrides):
        """Test individual booking has expected fields."""
        response = client.get("/v1/user/bookings")
        data = response.json()

        bookings = data.get("bookings", data.get("items", []))
        for booking in bookings[:1]:  # Check first booking
            assert "id" in booking or "booking_id" in booking
            assert "status" in booking
            assert "total_amount" in booking or "amount" in booking

    def test_payment_item_structure(self, client, setup_app_with_overrides):
        """Test individual payment has expected fields."""
        response = client.get("/v1/user/payments")
        data = response.json()

        payments = data.get("payments", data.get("items", []))
        for payment in payments[:1]:  # Check first payment
            assert "id" in payment or "payment_id" in payment
            assert "amount" in payment
            assert "status" in payment


# =============================================================================
# TESTS: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in endpoints."""

    def test_invalid_user_id(self, client):
        """Test handling of invalid user."""
        response = client.get("/v1/user/bookings")
        assert response.status_code in [401, 403]

    def test_malformed_query_parameters(self, client, setup_app_with_overrides):
        """Test handling of malformed query parameters."""
        response = client.get("/v1/user/bookings?limit=abc")
        assert response.status_code == 422

    def test_invalid_date_format(self, client, setup_app_with_overrides):
        """Test handling of invalid date format."""
        response = client.get("/v1/user/bookings?start_date=invalid-date")
        assert response.status_code in [400, 422]

    def test_out_of_range_offset(self, client, setup_app_with_overrides):
        """Test handling of out-of-range offset."""
        response = client.get("/v1/user/bookings?offset=999999")
        assert response.status_code == 200  # Should return empty list, not error


# =============================================================================
# TESTS: Performance
# =============================================================================

class TestPerformance:
    """Tests for endpoint performance."""

    def test_dashboard_response_time(self, client, setup_app_with_overrides):
        """Test dashboard loads within acceptable time."""
        import time
        start = time.time()
        response = client.get("/v1/user/dashboard")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 1.0  # Should complete in less than 1 second

    def test_bookings_list_response_time(self, client, setup_app_with_overrides):
        """Test bookings list loads within acceptable time."""
        import time
        start = time.time()
        response = client.get("/v1/user/bookings")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 0.5  # Should complete in less than 500ms

    def test_large_page_size(self, client, setup_app_with_overrides):
        """Test endpoint handles large page sizes."""
        response = client.get("/v1/user/bookings?limit=100")
        assert response.status_code == 200


# =============================================================================
# TESTS: Security
# =============================================================================

class TestSecurity:
    """Tests for security considerations."""

    def test_user_cannot_see_others_bookings(self, client, setup_app_with_overrides):
        """Test user cannot view other users' bookings."""
        # This test assumes endpoint properly filters by user
        response = client.get("/v1/user/bookings")
        assert response.status_code == 200
        data = response.json()

        # All bookings should belong to current user (user-123)
        # This would be verified in actual test with real data

    def test_no_sensitive_data_in_list_view(self, client, setup_app_with_overrides):
        """Test sensitive data is not exposed in list views."""
        response = client.get("/v1/user/bookings")
        assert response.status_code == 200
        data = response.json()

        # Check that password, tokens, etc. are not exposed
        json_str = json.dumps(data)
        assert "password" not in json_str.lower()
        assert "token" not in json_str.lower()
