"""
Unit tests for Telegram Bot Service
Tests user linking, conversation state, and booking completion flows.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from services.telegram_service import TelegramService
from database.models import User, TelegramConversationState


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def telegram_service(mock_db):
    """Create TelegramService instance with mock DB."""
    return TelegramService(mock_db)


class TestUserLinking:
    """Test user authentication linking flow."""

    @pytest.mark.asyncio
    async def test_create_auth_link_success(self, telegram_service, mock_db):
        """Test creating auth link for new telegram user."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = await telegram_service.create_auth_link(
            telegram_user_id="123456789",
            telegram_username="@rajkumar"
        )

        assert "link_token" in result
        assert "auth_url" in result
        assert result["expires_in_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_confirm_link_invalid_token(self, telegram_service, mock_db):
        """Test confirming link with non-existent token."""
        # Mock the execute().scalars().all() chain
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = await telegram_service.confirm_telegram_link("invalid-token", "user123")

        assert result["success"] == False
        assert "Invalid" in result["message"]


class TestConversationState:
    """Test conversation state management."""

    @pytest.mark.asyncio
    async def test_get_conversation_state_creates_new(self, telegram_service, mock_db):
        """Test creating new state if not found."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = await telegram_service.get_conversation_state("123456789")

        assert result.telegram_user_id == "123456789"
        assert result.current_state == "IDLE"
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_update_conversation_state(self, telegram_service, mock_db):
        """Test updating conversation state and context."""
        conv_state = Mock(spec=TelegramConversationState)
        conv_state.telegram_user_id = "123456789"
        conv_state.context = {}

        mock_db.execute.return_value.scalar_one_or_none.return_value = conv_state

        result = await telegram_service.update_conversation_state(
            "123456789",
            "AWAITING_CLASS",
            {"selected_train": "12345"}
        )

        assert result.current_state == "AWAITING_CLASS"
        assert result.context["selected_train"] == "12345"
        mock_db.commit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
