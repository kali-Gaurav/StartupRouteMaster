"""
Telegram Bot Tests
==================
Comprehensive tests for the Telegram bot system.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestIntentClassifier:
    """Tests for intent classification."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        from telegram_bot.intent_classifier import IntentClassifier
        return IntentClassifier()
    
    @pytest.mark.asyncio
    async def test_classify_start(self, classifier):
        """Test /start command classification."""
        result = await classifier.classify("/start")
        assert result.intent.value == "start"
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_classify_search_trains(self, classifier):
        """Test train search classification."""
        result = await classifier.classify("Search trains from Mumbai to Delhi")
        assert result.intent.value == "search_trains"
        assert result.confidence > 0.3
    
    @pytest.mark.asyncio
    async def test_classify_pnr(self, classifier):
        """Test PNR check classification."""
        result = await classifier.classify("Check PNR 1234567890")
        assert result.intent.value == "check_pnr"
        assert "pnr" in result.entities
    
    @pytest.mark.asyncio
    async def test_classify_sos(self, classifier):
        """Test SOS classification (highest priority)."""
        result = await classifier.classify("SOS emergency help")
        assert result.intent.value == "sos_emergency"
        assert result.confidence == 1.0
    
    @pytest.mark.asyncio
    async def test_classify_booking(self, classifier):
        """Test booking classification."""
        result = await classifier.classify("I want to book a ticket")
        assert result.intent.value == "book_ticket"
    
    @pytest.mark.asyncio
    async def test_entity_extraction(self, classifier):
        """Test entity extraction."""
        result = await classifier.classify("Trains from Mumbai to Delhi on 2026-04-25")
        assert "stations" in result.entities
        assert "date" in result.entities


class TestUserSessionManager:
    """Tests for user session management."""
    
    @pytest.fixture
    def session_manager(self):
        """Create session manager instance."""
        from telegram_bot.user_session_manager import UserSessionManager
        return UserSessionManager()
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test session creation."""
        session = await session_manager.get_session(chat_id=12345, user_id=67890)
        
        assert session.chat_id == 12345
        assert session.user_id == 67890
        assert session.context.state.value == "idle"
        assert session.message_count == 1
    
    @pytest.mark.asyncio
    async def test_update_state(self, session_manager):
        """Test state update."""
        await session_manager.update_state(chat_id=12345, state=UserState.SEARCHING)
        
        context = await session_manager.get_context(12345)
        assert context.state.value == "searching"
    
    @pytest.mark.asyncio
    async def test_clear_session(self, session_manager):
        """Test session clearing."""
        await session_manager.get_session(chat_id=12345, user_id=67890)
        result = await session_manager.clear_session(12345)
        
        assert result is True


class TestDispatcher:
    """Tests for Telegram dispatcher."""
    
    @pytest.fixture
    def dispatcher(self):
        """Create dispatcher instance."""
        from telegram_bot.dispatcher import TelegramDispatcher
        return TelegramDispatcher()
    
    def test_health_check(self, dispatcher):
        """Test health check."""
        health = dispatcher.health_check()
        
        assert "status" in health
        assert "circuit_breaker" in health
        assert "metrics" in health
    
    def test_get_metrics(self, dispatcher):
        """Test metrics retrieval."""
        metrics = dispatcher.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics


class TestKeyboards:
    """Tests for keyboard builders."""
    
    def test_main_menu(self):
        """Test main menu keyboard."""
        from telegram_bot.keyboards import keyboard_builder
        
        keyboard = keyboard_builder.main_menu()
        
        assert "keyboard" in keyboard
        assert len(keyboard["keyboard"]) == 3
    
    def test_search_menu(self):
        """Test search menu keyboard."""
        from telegram_bot.keyboards import keyboard_builder
        
        keyboard = keyboard_builder.search_menu()
        
        assert "keyboard" in keyboard
    
    def test_yes_no(self):
        """Test yes/no keyboard."""
        from telegram_bot.keyboards import keyboard_builder
        
        keyboard = keyboard_builder.yes_no()
        
        assert keyboard["one_time_keyboard"] is True
    
    def test_train_results_inline_keyboard(self):
        """Test inline keyboard for train results."""
        from telegram_bot.keyboards import keyboard_builder
        
        keyboards = keyboard_builder.train_search_results(
            train_no="12951",
            train_name="Mumbai Rajdhani",
            booking_id="123"
        )
        
        assert len(keyboards) == 2
        assert keyboards[0][0]["callback_data"].startswith("avail_")


class TestBot:
    """Tests for main bot."""
    
    @pytest.fixture
    def bot(self):
        """Create bot instance."""
        from telegram_bot.bot import TelegramBot
        return TelegramBot()
    
    def test_bot_initialization(self, bot):
        """Test bot initialization."""
        assert bot.is_running() is False
        assert bot.dispatcher is not None
        assert bot.router is not None
    
    def test_health_check(self, bot):
        """Test bot health check."""
        health = bot.get_health()
        
        assert "status" in health
        assert "dispatcher" in health
        assert "router" in health


class TestSchemas:
    """Tests for schema validation."""
    
    def test_telegram_user_schema(self):
        """Test Telegram user schema."""
        from telegram_bot.schemas import TelegramUser
        
        user = TelegramUser(
            id=12345,
            first_name="John",
            last_name="Doe",
            username="johndoe"
        )
        
        assert user.id == 12345
        assert user.first_name == "John"
    
    def test_bot_response_schema(self):
        """Test bot response schema."""
        from telegram_bot.schemas import BotResponse
        
        response = BotResponse(
            chat_id=12345,
            text="Hello!",
            parse_mode="HTML"
        )
        
        assert response.chat_id == 12345
        assert response.text == "Hello!"
        assert response.parse_mode == "HTML"
    
    def test_user_context_schema(self):
        """Test user context schema."""
        from telegram_bot.schemas import UserContext, UserState
        
        context = UserContext(
            chat_id=12345,
            user_id=67890,
            state=UserState.SEARCHING
        )
        
        assert context.chat_id == 12345
        assert context.state == UserState.SEARCHING


class TestConfig:
    """Tests for configuration."""
    
    def test_bot_config_from_env(self):
        """Test bot config from environment."""
        from telegram_bot.config import TelegramBotConfig
        
        config = TelegramBotConfig.from_env()
        
        assert hasattr(config, "bot_token")
        assert hasattr(config, "bot_mode")
        assert hasattr(config, "max_retries")
    
    def test_feature_config(self):
        """Test feature config."""
        from telegram_bot.config import FeatureConfig
        
        config = FeatureConfig.from_env()
        
        assert hasattr(config, "search_max_results")
        assert hasattr(config, "booking_max_passengers")


class TestHandlers:
    """Tests for command handlers."""
    
    @pytest.fixture
    def mock_message(self):
        """Create mock message."""
        message = Mock()
        message.chat = Mock()
        message.chat.id = 12345
        message.from_user = Mock()
        message.from_user.id = 67890
        message.from_user.first_name = "John"
        message.text = "test"
        message.location = None
        return message
    
    @pytest.mark.asyncio
    async def test_start_handler(self, mock_message):
        """Test start handler."""
        from telegram_bot.handlers.start_handler import StartHandler
        from telegram_bot.schemas import UserContext, IntentType
        
        handler = StartHandler()
        context = UserContext(chat_id=12345, user_id=67890)
        intent_result = Mock()
        intent_result.intent = IntentType.START
        
        result = await handler.handle(mock_message, context, intent_result)
        
        assert result.status.value == "success"
        assert result.response is not None
        assert result.response.chat_id == 12345
    
    @pytest.mark.asyncio
    async def test_help_handler(self, mock_message):
        """Test help handler."""
        from telegram_bot.handlers.help_handler import HelpHandler
        from telegram_bot.schemas import UserContext, IntentType
        
        handler = HelpHandler()
        context = UserContext(chat_id=12345, user_id=67890)
        intent_result = Mock()
        intent_result.intent = IntentType.HELP
        
        result = await handler.handle(mock_message, context, intent_result)
        
        assert result.status.value == "success"
        assert "Help" in result.response.text or "help" in result.response.text.lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])