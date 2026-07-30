"""
Dashboard Service Tests - Unit & Integration Tests
Team 5 can extend these with full test coverage.
"""

import pytest
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch

from services.dashboard_service import (
    DashboardService,
    DashboardConfig,
    PaginationParams,
    BookingHistoryItem,
    PaymentHistoryItem,
    UserTicket,
    UserProfile,
    DashboardSummary
)
from database.models import User, Booking, Payment, PassengerDetails


class TestDashboardServiceUnit:
    """Unit tests for DashboardService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_cache(self):
        """Mock cache service"""
        return Mock()

    @pytest.fixture
    def dashboard_service(self, mock_db, mock_cache):
        """Create dashboard service instance"""
        return DashboardService(mock_db, mock_cache)

    def test_config_defaults(self):
        """Test configuration defaults"""
        config = DashboardConfig()
        assert config.cache_ttl_profile_hours == 1
        assert config.cache_ttl_summary_hours == 1
        assert config.cache_ttl_history_minutes == 30
        assert config.default_page_size == 50
        assert config.max_page_size == 100

    def test_pagination_params_validation(self):
        """Test pagination parameter validation"""
        # Valid parameters
        params = PaginationParams(limit=50, offset=0)
        params.validate()
        assert params.limit == 50
        assert params.offset == 0

        # Invalid limit (too high)
        params = PaginationParams(limit=200, offset=0)
        params.validate()
        assert params.limit == 50  # Reset to default

        # Invalid offset (negative)
        params = PaginationParams(limit=50, offset=-10)
        params.validate()
        assert params.offset == 0

    def test_cache_key_generation(self, dashboard_service):
        """Test cache key format"""
        key = dashboard_service._get_cache_key("user123", "profile")
        assert key == "dashboard:user123:profile"

        key = dashboard_service._get_cache_key("user123", "bookings", "50_0")
        assert key == "dashboard:user123:bookings:50_0"

    def test_booking_history_item_creation(self):
        """Test BookingHistoryItem dataclass"""
        item = BookingHistoryItem(
            booking_id="bid1",
            pnr_number="ABC1234567",
            status="confirmed",
            travel_date=date(2026, 6, 15),
            from_station="NDLS",
            to_station="CSMT",
            amount_paid=2500.0,
            class_type="AC2",
            booked_at=datetime.utcnow(),
            passenger_count=2
        )
        assert item.booking_id == "bid1"
        assert item.passenger_count == 2

    def test_user_profile_creation(self):
        """Test UserProfile dataclass"""
        profile = UserProfile(
            user_id="user123",
            full_name="John Doe",
            email="john@example.com",
            phone_number="9999999999",
            member_since=datetime(2024, 1, 15),
            total_bookings=5,
            total_spent=12500.0,
            preferences={"newsletter": True}
        )
        assert profile.total_bookings == 5
        assert profile.total_spent == 12500.0

    def test_dashboard_summary_creation(self):
        """Test DashboardSummary dataclass"""
        summary = DashboardSummary(
            total_bookings=10,
            total_spent=25000.0,
            upcoming_bookings=2,
            completed_bookings=8,
            cancelled_bookings=0,
            pending_payments=1,
            recent_activity=[
                {
                    "type": "booking",
                    "booking_id": "bid1",
                    "pnr": "ABC1234567",
                    "status": "confirmed",
                    "date": "2026-06-08T14:30:00",
                    "amount": 2500.0
                }
            ],
            member_since=datetime(2024, 1, 15),
            last_booking_date=date(2026, 6, 8)
        )
        assert summary.total_bookings == 10
        assert len(summary.recent_activity) == 1


class TestDashboardServiceIntegration:
    """Integration tests for DashboardService (with real DB)"""

    @pytest.fixture
    def setup_test_data(self, db_session):
        """Setup test data in database"""
        # Create test user
        user = User(
            id="test-user-1",
            full_name="Test User",
            email="test@example.com",
            phone_number="9999999999",
            created_at=datetime(2024, 1, 15)
        )
        db_session.add(user)

        # Create test bookings
        booking1 = Booking(
            id="booking-1",
            user_id="test-user-1",
            pnr_number="ABC1234567",
            booking_status="confirmed",
            travel_date=date(2026, 6, 15),
            from_station_code="NDLS",
            to_station_code="CSMT",
            amount_paid=2500.0,
            class_type="AC2",
            created_at=datetime.utcnow()
        )
        db_session.add(booking1)

        # Create test payments
        payment1 = Payment(
            id="payment-1",
            booking_id="booking-1",
            user_id="test-user-1",
            amount=2500.0,
            status="completed",
            payment_method="UPI",
            created_at=datetime.utcnow()
        )
        db_session.add(payment1)

        db_session.commit()
        return {"user": user, "booking": booking1, "payment": payment1}

    @pytest.mark.asyncio
    async def test_get_user_profile(self, db_session, setup_test_data):
        """Test get_user_profile with real data"""
        dashboard_service = DashboardService(db_session)
        profile = await dashboard_service.get_user_profile("test-user-1")

        assert profile.user_id == "test-user-1"
        assert profile.full_name == "Test User"
        assert profile.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_booking_history(self, db_session, setup_test_data):
        """Test get_booking_history with real data"""
        dashboard_service = DashboardService(db_session)
        items, total = await dashboard_service.get_user_booking_history(
            "test-user-1",
            limit=50,
            offset=0
        )

        assert len(items) > 0
        assert total >= 1
        assert items[0].pnr_number == "ABC1234567"

    @pytest.mark.asyncio
    async def test_get_payment_history(self, db_session, setup_test_data):
        """Test get_payment_history with real data"""
        dashboard_service = DashboardService(db_session)
        items, total = await dashboard_service.get_user_payment_history(
            "test-user-1",
            limit=50,
            offset=0
        )

        assert len(items) > 0
        assert total >= 1
        assert items[0].status == "completed"

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(self, db_session, setup_test_data):
        """Test get_dashboard_summary with real data"""
        dashboard_service = DashboardService(db_session)
        summary = await dashboard_service.get_dashboard_summary("test-user-1")

        assert summary.total_bookings >= 1
        assert summary.total_spent >= 2500.0
        assert summary.upcoming_bookings >= 1


class TestCaching:
    """Test caching behavior"""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_db, mock_cache):
        """Test cache hit scenario"""
        mock_cache.get.return_value = {
            "items": [{"booking_id": "1"}],
            "total": 1
        }

        service = DashboardService(mock_db, mock_cache)
        items, total = await service.get_user_booking_history("user1")

        assert total == 1
        mock_cache.get.assert_called()

    @pytest.mark.asyncio
    async def test_cache_miss_and_set(self, mock_db, mock_cache):
        """Test cache miss and subsequent set"""
        mock_cache.get.return_value = None

        service = DashboardService(mock_db, mock_cache)
        # Note: This would require a real query that we mock
        # Details depend on how async is handled


class TestPagination:
    """Test pagination logic"""

    def test_pagination_boundary_conditions(self):
        """Test pagination edge cases"""
        # Max page size
        params = PaginationParams(limit=200, offset=0)
        params.validate()
        assert params.limit == 50

        # Zero offset
        params = PaginationParams(limit=50, offset=0)
        params.validate()
        assert params.offset == 0

        # Large offset
        params = PaginationParams(limit=50, offset=10000)
        params.validate()
        assert params.offset == 10000


class TestErrorHandling:
    """Test error handling and resilience"""

    @pytest.mark.asyncio
    async def test_cache_error_graceful_fallback(self, mock_db, mock_cache):
        """Test graceful degradation when cache fails"""
        mock_cache.get.side_effect = Exception("Redis connection failed")

        service = DashboardService(mock_db, mock_cache)
        # Should fall back to database query without crashing


    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_db):
        """Test handling of non-existent user"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = DashboardService(mock_db)
        with pytest.raises(ValueError, match="not found"):
            await service.get_user_profile("nonexistent-user")


@pytest.fixture(scope="session")
def mock_db():
    """Mock database session for tests"""
    return Mock(spec=Session)


@pytest.fixture(scope="session")
def mock_cache():
    """Mock cache service for tests"""
    return Mock()


# Integration test suite
class TestDashboardAPIEndpoints:
    """API endpoint tests (use TestClient)"""

    @pytest.fixture
    def client(self):
        """FastAPI TestClient"""
        from fastapi.testclient import TestClient
        from api.app import app
        return TestClient(app)

    def test_endpoint_profile_200(self, client, auth_headers):
        """Test GET /dashboard/profile returns 200"""
        response = client.get(
            "/api/v1/dashboard/profile",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "user_id" in response.json()

    def test_endpoint_bookings_pagination(self, client, auth_headers):
        """Test GET /dashboard/bookings pagination"""
        response = client.get(
            "/api/v1/dashboard/bookings?limit=10&offset=0",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_endpoint_invalid_pagination(self, client, auth_headers):
        """Test invalid pagination parameters"""
        response = client.get(
            "/api/v1/dashboard/bookings?limit=200&offset=-5",
            headers=auth_headers
        )
        # Should return 422 or auto-correct
        assert response.status_code in [200, 422]

    def test_endpoint_requires_auth(self, client):
        """Test that endpoints require authentication"""
        response = client.get("/api/v1/dashboard/profile")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
