"""
Unit tests for NotificationLog model.
Tests for Task 1.1.5: Create notification_logs table
Reference: REQ-015 (Notification Retry Logic)
"""
import pytest
from datetime import datetime
import uuid
from unittest.mock import MagicMock, patch


class TestNotificationLogModel:
    """Test cases for NotificationLog model."""

    def test_notification_log_creation(self):
        """Test creating a NotificationLog instance with required fields."""
        from database.models import NotificationLog
        
        notification_id = str(uuid.uuid4())
        booking_id = str(uuid.uuid4())
        channel = "SMS"
        status = "pending"
        
        notification = NotificationLog(
            notification_id=notification_id,
            booking_id=booking_id,
            channel=channel,
            status=status
        )
        
        assert notification.notification_id == notification_id
        assert notification.booking_id == booking_id
        assert notification.channel == channel
        assert notification.status == status
        # Note: retry_count default is applied at database level, not Python level
        # The column has default=0 defined, but Python objects don't get defaults automatically
        assert notification.retry_count is None or notification.retry_count == 0
        assert notification.error_message is None

    def test_notification_log_with_all_fields(self):
        """Test creating a NotificationLog with all fields populated."""
        from database.models import NotificationLog
        
        notification_id = str(uuid.uuid4())
        booking_id = str(uuid.uuid4())
        error_msg = "SMS provider timeout after 30 seconds"
        
        notification = NotificationLog(
            notification_id=notification_id,
            booking_id=booking_id,
            channel="EMAIL",
            status="failed",
            retry_count=3,
            error_message=error_msg
        )
        
        assert notification.notification_id == notification_id
        assert notification.booking_id == booking_id
        assert notification.channel == "EMAIL"
        assert notification.status == "failed"
        assert notification.retry_count == 3
        assert notification.error_message == error_msg

    def test_notification_log_default_values(self):
        """Test that default values are defined in the model."""
        from database.models import NotificationLog
        
        # Get the column defaults from the mapper
        status_column = NotificationLog.__mapper__.columns['status']
        retry_count_column = NotificationLog.__mapper__.columns['retry_count']
        created_at_column = NotificationLog.__mapper__.columns['created_at']
        
        # Check that defaults are defined (they are applied on database insert)
        assert status_column.default is not None
        assert str(status_column.default.arg) == "pending"
        assert retry_count_column.default is not None
        assert retry_count_column.default.arg == 0
        assert created_at_column.default is not None

    def test_notification_log_status_values(self):
        """Test various notification status values."""
        from database.models import NotificationLog
        
        valid_statuses = ["pending", "sent", "delivered", "failed"]
        
        for status in valid_statuses:
            notification = NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel="SMS",
                status=status
            )
            assert notification.status == status

    def test_notification_log_channel_values(self):
        """Test various notification channel values."""
        from database.models import NotificationLog
        
        valid_channels = ["SMS", "EMAIL", "PUSH", "WHATSAPP", "TELEGRAM"]
        
        for channel in valid_channels:
            notification = NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel=channel
            )
            assert notification.channel == channel

    def test_notification_log_retry_count_increment(self):
        """Test retry count increment for failed notifications."""
        from database.models import NotificationLog
        
        notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            channel="SMS",
            status="failed",
            retry_count=0
        )
        
        # Simulate retry logic
        notification.retry_count += 1
        assert notification.retry_count == 1
        
        notification.retry_count += 1
        assert notification.retry_count == 2
        
        notification.retry_count += 1
        assert notification.retry_count == 3

    def test_notification_log_optional_fields(self):
        """Test that optional fields can be None."""
        from database.models import NotificationLog
        
        notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            channel="PUSH"
        )
        
        assert notification.booking_id is None
        assert notification.error_message is None

    def test_notification_log_indexes(self):
        """Test that indexes are defined correctly."""
        from database.models import NotificationLog
        
        # Check that table args contains the expected indexes
        table_args = NotificationLog.__table_args__
        
        # Convert to list of tuples for easier inspection
        indexes = [arg for arg in table_args if hasattr(arg, 'name')]
        index_names = [idx.name for idx in indexes]
        
        assert 'ix_notification_logs_booking_id' in index_names
        assert 'ix_notification_logs_status' in index_names
        assert 'ix_notification_logs_channel' in index_names
        assert 'ix_notification_logs_created_at' in index_names

    def test_notification_log_table_name(self):
        """Test that the table name is correct."""
        from database.models import NotificationLog
        
        assert NotificationLog.__tablename__ == "notification_logs"

    def test_notification_log_relationship(self):
        """Test that the booking relationship is defined."""
        from database.models import NotificationLog
        
        # Check that the relationship exists
        assert hasattr(NotificationLog, 'booking')
        
        # The relationship should be a relationship object
        assert NotificationLog.booking is not None

    def test_notification_log_timestamps(self):
        """Test that timestamp columns are defined in the model."""
        from database.models import NotificationLog
        
        # Check that the timestamp columns exist and have defaults defined
        created_at_column = NotificationLog.__mapper__.columns['created_at']
        updated_at_column = NotificationLog.__mapper__.columns['updated_at']
        
        # The columns should have default values defined (applied on database insert)
        assert created_at_column.default is not None
        assert updated_at_column.default is not None
        # updated_at should have onupdate defined
        assert updated_at_column.onupdate is not None

    def test_notification_log_uuid_generation(self):
        """Test that notification_id column has a default generator defined."""
        from database.models import NotificationLog
        
        # Check that the notification_id column has a default function defined
        notification_id_column = NotificationLog.__mapper__.columns['notification_id']
        
        # The column should have a default function that generates UUIDs
        assert notification_id_column.default is not None
        assert notification_id_column.primary_key == True

    def test_notification_log_repr(self):
        """Test the string representation of NotificationLog."""
        from database.models import NotificationLog
        
        notification_id = str(uuid.uuid4())
        notification = NotificationLog(
            notification_id=notification_id,
            channel="SMS",
            status="pending"
        )
        
        repr_str = repr(notification)
        # Check that it's a valid object representation
        assert "NotificationLog" in repr_str
        assert notification_id in repr_str


class TestNotificationLogIntegration:
    """Integration tests for NotificationLog with database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = MagicMock()
        return session

    def test_add_notification_log_to_session(self, mock_session):
        """Test adding a NotificationLog to a database session."""
        from database.models import NotificationLog
        
        notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            channel="EMAIL",
            status="pending"
        )
        
        mock_session.add(notification)
        mock_session.add.assert_called_once_with(notification)

    def test_query_notification_logs_by_booking_id(self, mock_session):
        """Test querying notification logs by booking_id."""
        from database.models import NotificationLog
        
        # This tests the index usage
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        result = mock_session.query(NotificationLog).filter(
            NotificationLog.booking_id == "test-booking-id"
        ).all()
        
        assert result == []

    def test_query_notification_logs_by_status(self, mock_session):
        """Test querying notification logs by status for retry processing."""
        from database.models import NotificationLog
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        # Query for failed notifications that need retry
        result = mock_session.query(NotificationLog).filter(
            NotificationLog.status == "failed"
        ).all()
        
        assert result == []

    def test_query_notification_logs_by_channel(self, mock_session):
        """Test querying notification logs by channel."""
        from database.models import NotificationLog
        
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        result = mock_session.query(NotificationLog).filter(
            NotificationLog.channel == "SMS"
        ).all()
        
        assert result == []


class TestNotificationLogRetryLogic:
    """Tests for notification retry logic functionality."""

    def test_retry_logic_max_retries(self):
        """Test that retry count tracks attempts correctly."""
        from database.models import NotificationLog
        
        max_retries = 3
        
        notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            channel="SMS",
            status="failed",
            retry_count=0
        )
        
        # Simulate retry attempts
        for i in range(max_retries + 1):
            if notification.retry_count < max_retries:
                notification.retry_count += 1
                notification.status = "pending"
            else:
                notification.status = "failed_permanent"
        
        assert notification.retry_count == max_retries
        assert notification.status == "failed_permanent"

    def test_retry_logic_status_transitions(self):
        """Test status transitions during retry logic."""
        from database.models import NotificationLog
        
        # Initial state
        notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            channel="EMAIL",
            status="pending"
        )
        
        # First attempt
        notification.status = "sent"
        assert notification.status == "sent"
        
        # Delivery confirmed
        notification.status = "delivered"
        assert notification.status == "delivered"

    def test_error_message_tracking(self):
        """Test error message tracking for failed notifications."""
        from database.models import NotificationLog
        
        error_messages = [
            "SMS provider timeout after 30 seconds",
            "Email server rejected: Invalid recipient",
            "Push notification token expired",
            None
        ]
        
        for error_msg in error_messages:
            notification = NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel="SMS",
                status="failed",
                error_message=error_msg
            )
            assert notification.error_message == error_msg

    def test_booking_notification_tracking(self):
        """Test that notifications can be linked to bookings."""
        from database.models import NotificationLog
        
        booking_id = str(uuid.uuid4())
        
        # Create notifications for different channels for the same booking
        sms_notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            booking_id=booking_id,
            channel="SMS",
            status="delivered"
        )
        
        email_notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            booking_id=booking_id,
            channel="EMAIL",
            status="delivered"
        )
        
        push_notification = NotificationLog(
            notification_id=str(uuid.uuid4()),
            booking_id=booking_id,
            channel="PUSH",
            status="pending"
        )
        
        assert sms_notification.booking_id == booking_id
        assert email_notification.booking_id == booking_id
        assert push_notification.booking_id == booking_id

    def test_retry_count_for_different_channels(self):
        """Test retry count behavior for different notification channels."""
        from database.models import NotificationLog
        
        channels = ["SMS", "EMAIL", "PUSH"]
        
        for channel in channels:
            notification = NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel=channel,
                status="failed",
                retry_count=0
            )
            
            # Different channels might have different retry strategies
            if channel == "SMS":
                max_retries = 3
            elif channel == "EMAIL":
                max_retries = 5
            else:
                max_retries = 2
            
            notification.retry_count = max_retries
            assert notification.retry_count == max_retries


class TestNotificationLogAnalytics:
    """Tests for notification analytics and reporting."""

    def test_notification_delivery_stats(self):
        """Test calculating notification delivery statistics."""
        from database.models import NotificationLog
        
        notifications = [
            NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel="SMS",
                status="delivered"
            ),
            NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel="SMS",
                status="delivered"
            ),
            NotificationLog(
                notification_id=str(uuid.uuid4()),
                channel="SMS",
                status="failed"
            ),
        ]
        
        total = len(notifications)
        delivered = sum(1 for n in notifications if n.status == "delivered")
        failed = sum(1 for n in notifications if n.status == "failed")
        
        assert total == 3
        assert delivered == 2
        assert failed == 1

    def test_notification_channel_distribution(self):
        """Test calculating notification distribution by channel."""
        from database.models import NotificationLog
        
        notifications = [
            NotificationLog(notification_id=str(uuid.uuid4()), channel="SMS"),
            NotificationLog(notification_id=str(uuid.uuid4()), channel="EMAIL"),
            NotificationLog(notification_id=str(uuid.uuid4()), channel="SMS"),
            NotificationLog(notification_id=str(uuid.uuid4()), channel="PUSH"),
            NotificationLog(notification_id=str(uuid.uuid4()), channel="EMAIL"),
        ]
        
        channel_counts = {}
        for notification in notifications:
            channel_counts[notification.channel] = channel_counts.get(notification.channel, 0) + 1
        
        assert channel_counts["SMS"] == 2
        assert channel_counts["EMAIL"] == 2
        assert channel_counts["PUSH"] == 1

    def test_notification_failure_rate(self):
        """Test calculating notification failure rate."""
        from database.models import NotificationLog
        
        notifications = [
            NotificationLog(notification_id=str(uuid.uuid4()), status="delivered"),
            NotificationLog(notification_id=str(uuid.uuid4()), status="delivered"),
            NotificationLog(notification_id=str(uuid.uuid4()), status="failed"),
            NotificationLog(notification_id=str(uuid.uuid4()), status="failed"),
            NotificationLog(notification_id=str(uuid.uuid4()), status="pending"),
        ]
        
        total = len(notifications)
        failed = sum(1 for n in notifications if n.status == "failed")
        failure_rate = failed / total
        
        assert total == 5
        assert failed == 2
        assert failure_rate == 0.4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])