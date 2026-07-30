import sys
import os
import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

# Add backend to sys.path so scripts can resolve imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import database and models, with fallback for testing
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Test database setup
    @pytest.fixture(scope="session")
    def db_engine():
        """Create test database engine."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False}
        )
        yield engine
        engine.dispose()

    @pytest.fixture
    def db_session(db_engine):
        """Create test database session."""
        from sqlalchemy.orm import Session
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = TestingSessionLocal()
        yield session
        session.rollback()
        session.close()

except ImportError:
    @pytest.fixture
    def db_session():
        """Fallback mock database session."""
        return MagicMock()


# HTTP Client fixture
@pytest.fixture
async def async_client(db_session):
    """Create async HTTP client for testing."""
    try:
        from httpx import AsyncClient
        from main import app

        def override_get_db():
            yield db_session

        from database import get_db
        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

        app.dependency_overrides.clear()
    except ImportError:
        # Fallback for testing without full app
        mock_client = AsyncMock()
        yield mock_client


# User fixtures
@pytest.fixture
def mock_user(db_session):
    """Create a mock user."""
    try:
        from database.models import User

        user = User(
            id=str(uuid.uuid4()),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            name="Test User",
            phone="+91-9999999999",
            password_hash="hashed_password",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )

        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    except:
        # Fallback mock
        mock_user = MagicMock()
        mock_user.id = str(uuid.uuid4())
        mock_user.email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        mock_user.name = "Test User"
        return mock_user


@pytest.fixture
def mock_another_user(db_session):
    """Create another mock user."""
    try:
        from database.models import User

        user = User(
            id=str(uuid.uuid4()),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            name="Another User",
            phone="+91-8888888888",
            password_hash="hashed_password",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )

        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    except:
        mock_user = MagicMock()
        mock_user.id = str(uuid.uuid4())
        return mock_user


# Route and booking fixtures
@pytest.fixture
def mock_route(db_session):
    """Create a mock route."""
    try:
        from database.models import PrecalculatedRoute

        route = PrecalculatedRoute(
            id=str(uuid.uuid4()),
            route_data={"source": "Delhi", "destination": "Mumbai", "segments": []},
            src="DEL",
            dest="BOM",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(route)
        db_session.commit()
        db_session.refresh(route)
        return route
    except:
        mock_route = MagicMock()
        mock_route.id = str(uuid.uuid4())
        mock_route.src = "DEL"
        mock_route.dest = "BOM"
        return mock_route


@pytest.fixture
def mock_booking(db_session, mock_user, mock_route):
    """Create a mock booking."""
    try:
        from database.models import Booking

        booking = Booking(
            id=str(uuid.uuid4()),
            user_id=mock_user.id,
            route_id=mock_route.id,
            booking_status="initiated",
            pnr_number=f"PNR{uuid.uuid4().hex[:10].upper()}",
            amount_paid=500.0,
            travel_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(booking)
        db_session.commit()
        db_session.refresh(booking)
        return booking
    except:
        mock_booking = MagicMock()
        mock_booking.id = str(uuid.uuid4())
        mock_booking.user_id = mock_user.id
        mock_booking.booking_status = "initiated"
        return mock_booking


# Payment fixtures
@pytest.fixture
def mock_payment(db_session, mock_booking, mock_user):
    """Create a mock payment."""
    try:
        from database.models import Payment
        from schemas.payment import PaymentStatus

        payment = Payment(
            id=str(uuid.uuid4()),
            booking_id=mock_booking.id,
            user_id=mock_user.id,
            amount=500.0,
            payment_method="upi",
            status=PaymentStatus.PENDING.value,
            razorpay_order_id=f"order_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        return payment
    except:
        mock_payment = MagicMock()
        mock_payment.id = str(uuid.uuid4())
        mock_payment.booking_id = mock_booking.id
        mock_payment.user_id = mock_user.id
        mock_payment.amount = 500.0
        mock_payment.status = "pending"
        mock_payment.razorpay_order_id = f"order_{uuid.uuid4().hex[:12]}"
        return mock_payment


@pytest.fixture
def mock_completed_payment(db_session, mock_booking, mock_user):
    """Create a completed payment."""
    try:
        from database.models import Payment
        from schemas.payment import PaymentStatus

        payment = Payment(
            id=str(uuid.uuid4()),
            booking_id=mock_booking.id,
            user_id=mock_user.id,
            amount=500.0,
            payment_method="upi",
            status=PaymentStatus.SUCCESS.value,
            razorpay_order_id=f"order_{uuid.uuid4().hex[:12]}",
            razorpay_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            transaction_id=f"txn_{uuid.uuid4().hex[:8]}",
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        return payment
    except:
        mock_payment = MagicMock()
        mock_payment.id = str(uuid.uuid4())
        mock_payment.status = "completed"
        return mock_payment


@pytest.fixture
def mock_failed_payment(db_session, mock_booking, mock_user):
    """Create a failed payment."""
    try:
        from database.models import Payment
        from schemas.payment import PaymentStatus

        payment = Payment(
            id=str(uuid.uuid4()),
            booking_id=mock_booking.id,
            user_id=mock_user.id,
            amount=500.0,
            payment_method="upi",
            status=PaymentStatus.FAILED.value,
            razorpay_order_id=f"order_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        return payment
    except:
        mock_payment = MagicMock()
        mock_payment.id = str(uuid.uuid4())
        mock_payment.status = "failed"
        return mock_payment


@pytest.fixture
def mock_refund(db_session, mock_completed_payment):
    """Create a mock refund."""
    try:
        from database.models import Payment
        from schemas.payment import PaymentStatus

        refund = Payment(
            id=str(uuid.uuid4()),
            booking_id=mock_completed_payment.booking_id,
            amount=-mock_completed_payment.amount,
            payment_method=mock_completed_payment.payment_method,
            status=PaymentStatus.REFUNDED.value,
            original_payment_id=mock_completed_payment.id,
            refund_reason="customer_request",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(refund)
        db_session.commit()
        db_session.refresh(refund)
        return refund
    except:
        mock_refund = MagicMock()
        mock_refund.id = str(uuid.uuid4())
        return mock_refund


# Event loop fixture
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock service fixtures
@pytest.fixture
def mock_email_service():
    """Mock email service."""
    return MagicMock()


@pytest.fixture
def mock_sms_service():
    """Mock SMS service."""
    return MagicMock()


@pytest.fixture
def mock_inventory_service():
    """Mock inventory service."""
    service = AsyncMock()
    service.confirm_seats = AsyncMock(return_value=True)
    service.release_seats = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_razorpay_client():
    """Mock Razorpay client."""
    client = MagicMock()
    client.create_order = MagicMock(return_value={"id": f"order_{uuid.uuid4().hex[:12]}"})
    return client


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "security: mark test as a security test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
