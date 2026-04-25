"""
Test Configuration
==================
Pytest fixtures and configuration for Telegram bot tests.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_telegram_message():
    """Create a mock Telegram message."""
    message = Mock()
    message.message_id = 12345
    message.chat = Mock()
    message.chat.id = 67890
    message.chat.type = "private"
    message.from_user = Mock()
    message.from_user.id = 67890
    message.from_user.is_bot = False
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.from_user.username = "testuser"
    message.from_user.language_code = "en"
    message.date = Mock()
    message.date.timestamp = lambda: 1234567890
    message.text = "test message"
    message.message_type = "text"
    message.location = None
    message.contact = None
    message.reply_to_message = None
    return message


@pytest.fixture
def mock_callback_query():
    """Create a mock callback query."""
    callback = Mock()
    callback.id = "callback_123"
    callback.from_user = Mock()
    callback.from_user.id = 67890
    callback.from_user.first_name = "Test"
    callback.message = Mock()
    callback.message.chat = Mock()
    callback.message.chat.id = 67890
    callback.data = "test_callback"
    return callback


@pytest.fixture
def mock_user_context():
    """Create a mock user context."""
    from telegram_bot.schemas import UserContext, UserState, IntentType
    return UserContext(
        chat_id=67890,
        user_id=12345,
        state=UserState.IDLE,
        intent=IntentType.UNKNOWN,
        data={},
        history=[]
    )


@pytest.fixture
def mock_intent_result():
    """Create a mock intent result."""
    from telegram_bot.intent_classifier import IntentResult
    from telegram_bot.schemas import IntentType
    return IntentResult(
        intent=IntentType.UNKNOWN,
        confidence=0.5,
        entities={},
        raw_text="test"
    )


@pytest.fixture
def mock_dispatcher():
    """Create a mock dispatcher."""
    dispatcher = Mock()
    dispatcher.send_message = AsyncMock(return_value=True)
    dispatcher.send_document = AsyncMock(return_value=True)
    dispatcher.send_photo = AsyncMock(return_value=True)
    dispatcher.edit_message = AsyncMock(return_value=True)
    dispatcher.delete_message = AsyncMock(return_value=True)
    dispatcher.answer_callback = AsyncMock(return_value=True)
    dispatcher.get_me = AsyncMock(return_value={"ok": True, "result": {"id": 123, "username": "testbot"}})
    dispatcher.close = AsyncMock()
    dispatcher.health_check = Mock(return_value={"status": "healthy"})
    dispatcher.get_metrics = Mock(return_value={"total_operations": 0})
    return dispatcher


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    from telegram_bot.schemas import UserContext, UserState
    from telegram_bot.user_session_manager import UserSession
    
    session = Mock()
    session.chat_id = 67890
    session.user_id = 12345
    session.context = UserContext(
        chat_id=67890,
        user_id=12345,
        state=UserState.IDLE
    )
    session.created_at = Mock()
    session.last_activity = Mock()
    session.message_count = 0
    session.is_active = True
    
    return session


@pytest.fixture
def sample_update():
    """Create a sample Telegram update."""
    return {
        "update_id": 12345,
        "message": {
            "message_id": 67890,
            "from": {
                "id": 12345,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser"
            },
            "chat": {
                "id": 12345,
                "type": "private"
            },
            "date": 1234567890,
            "text": "/start"
        }
    }


@pytest.fixture
def sample_callback_update():
    """Create a sample callback update."""
    return {
        "update_id": 12346,
        "callback_query": {
            "id": "callback_123",
            "from": {
                "id": 12345,
                "is_bot": False,
                "first_name": "Test"
            },
            "message": {
                "message_id": 67891,
                "chat": {
                    "id": 12345,
                    "type": "private"
                }
            },
            "data": "book_12951"
        }
    }


@pytest.fixture
def sample_search_result():
    """Create sample search results."""
    return [
        {
            "train_no": "12951",
            "train_name": "Mumbai Rajdhani",
            "departure": "16:55",
            "arrival": "08:35",
            "duration": "15h 40m",
            "classes": ["1A", "2A", "3A"]
        },
        {
            "train_no": "12909",
            "train_name": "Garib Rath",
            "departure": "18:40",
            "arrival": "10:25",
            "duration": "15h 45m",
            "classes": ["3A", "CC"]
        }
    ]


@pytest.fixture
def sample_booking_data():
    """Create sample booking data."""
    return {
        "train_no": "12951",
        "train_name": "Mumbai Rajdhani",
        "class": "AC 3-Tier (3A)",
        "quota": "General",
        "passengers": [
            {"name": "John Doe", "age": 25, "gender": "M"},
            {"name": "Jane Doe", "age": 23, "gender": "F"}
        ]
    }