"""
Integration Tests for Telegram Bot
===================================
End-to-end tests for the complete bot system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBotIntegration:
    """Integration tests for the complete bot system."""
    
    @pytest.fixture
    def bot(self):
        """Create bot instance for testing."""
        from telegram_bot.bot import TelegramBot
        return TelegramBot()
    
    @pytest.mark.asyncio
    async def test_process_text_message(self, bot, sample_update):
        """Test processing a text message."""
        with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await bot.process_update(sample_update)
            
            assert result is not None
            assert result.chat_id == sample_update["message"]["chat"]["id"]
    
    @pytest.mark.asyncio
    async def test_process_callback_query(self, bot, sample_callback_update):
        """Test processing a callback query."""
        with patch.object(bot.dispatcher, 'answer_callback', new_callable=AsyncMock) as mock_answer:
            with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
                mock_answer.return_value = True
                mock_send.return_value = True
                
                result = await bot.process_update(sample_callback_update)
                
                mock_answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_command_flow(self, bot):
        """Test the complete /start command flow."""
        start_update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "date": 1234567890,
                "text": "/start"
            }
        }
        
        with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await bot.process_update(start_update)
            
            assert result is not None
            assert "Welcome" in result.text or "Welcome back" in result.text
    
    @pytest.mark.asyncio
    async def test_search_train_flow(self, bot):
        """Test the train search flow."""
        search_update = {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "date": 1234567890,
                "text": "Trains from Mumbai to Delhi"
            }
        }
        
        with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await bot.process_update(search_update)
            
            assert result is not None
            assert "search" in result.text.lower() or "train" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_pnr_check_flow(self, bot):
        """Test the PNR check flow."""
        pnr_update = {
            "update_id": 3,
            "message": {
                "message_id": 3,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "date": 1234567890,
                "text": "Check PNR 1234567890"
            }
        }
        
        with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await bot.process_update(pnr_update)
            
            assert result is not None


class TestDispatcherIntegration:
    """Integration tests for dispatcher."""
    
    @pytest.fixture
    def dispatcher(self):
        """Create dispatcher instance."""
        from telegram_bot.dispatcher import TelegramDispatcher
        return TelegramDispatcher()
    
    @pytest.mark.asyncio
    async def test_send_message_success(self, dispatcher):
        """Test successful message sending."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json = Mock(return_value={"ok": True})
            mock_post.return_value = mock_response
            
            result = await dispatcher.send_message(
                chat_id=12345,
                text="Test message"
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_send_message_with_keyboard(self, dispatcher):
        """Test message with keyboard."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json = Mock(return_value={"ok": True})
            mock_post.return_value = mock_response
            
            keyboard = {"keyboard": [["Button1"]]}
            result = await dispatcher.send_message(
                chat_id=12345,
                text="Test",
                keyboard=keyboard
            )
            
            assert result is True


class TestSessionIntegration:
    """Integration tests for session management."""
    
    @pytest.fixture
    def session_manager(self):
        """Create session manager instance."""
        from telegram_bot.user_session_manager import UserSessionManager
        return UserSessionManager()
    
    @pytest.mark.asyncio
    async def test_session_persistence(self, session_manager):
        """Test session persistence across calls."""
        chat_id = 99999
        
        # Create session
        session1 = await session_manager.get_session(chat_id, 12345)
        assert session1.message_count == 1
        
        # Get same session
        session2 = await session_manager.get_session(chat_id, 12345)
        assert session2.message_count == 2
        
        # Update state
        await session_manager.update_state(chat_id, "searching")
        
        # Verify update
        context = await session_manager.get_context(chat_id)
        assert context.state.value == "searching"
        
        # Cleanup
        await session_manager.clear_session(chat_id)


class TestHandlerIntegration:
    """Integration tests for handlers."""
    
    @pytest.mark.asyncio
    async def test_search_handler_with_entities(self):
        """Test search handler with extracted entities."""
        from telegram_bot.handlers.search_handler import SearchHandler
        from telegram_bot.schemas import UserContext, IntentType
        from telegram_bot.intent_classifier import IntentResult
        
        handler = SearchHandler()
        context = UserContext(chat_id=12345, user_id=67890)
        
        intent_result = IntentResult(
            intent=IntentType.SEARCH_TRAINS,
            confidence=0.8,
            entities={
                "stations": {"from": "Mumbai", "to": "Delhi"},
                "date": "2026-04-25"
            },
            raw_text="Trains from Mumbai to Delhi on 2026-04-25"
        )
        
        mock_message = Mock()
        mock_message.chat = Mock()
        mock_message.chat.id = 12345
        mock_message.text = "Trains from Mumbai to Delhi"
        
        with patch('telegram_bot.handlers.search_handler.search_service') as mock_service:
            mock_service.search_trains = AsyncMock(return_value=[])
            
            result = await handler.handle(mock_message, context, intent_result)
            
            assert result.status.value in ["success", "failed", "needs_input"]


class TestRouterIntegration:
    """Integration tests for command router."""
    
    @pytest.fixture
    def router(self):
        """Create router instance."""
        from telegram_bot.command_router import CommandRouter
        return CommandRouter()
    
    @pytest.mark.asyncio
    async def test_route_unknown_intent(self, router):
        """Test routing unknown intent to fallback."""
        from telegram_bot.schemas import TelegramMessage, UserContext, IntentType
        from telegram_bot.intent_classifier import IntentResult
        
        mock_message = Mock()
        mock_message.chat = Mock()
        mock_message.chat.id = 12345
        mock_message.text = "asdfghjkl"
        mock_message.from_user = Mock()
        mock_message.from_user.id = 67890
        
        context = UserContext(chat_id=12345, user_id=67890)
        intent_result = IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.1,
            entities={},
            raw_text="asdfghjkl"
        )
        
        with patch.object(router.session_manager, 'get_session', new_callable=AsyncMock) as mock_session:
            mock_session.return_value = Mock(
                context=context,
                message_count=0
            )
            
            result = await router.route(mock_message, 12345, 67890)
            
            assert result is not None


class TestResilienceIntegration:
    """Integration tests for resilience patterns."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with dispatcher."""
        from telegram_bot.dispatcher import TelegramDispatcher
        from core.resilience.core import circuit_manager
        
        dispatcher = TelegramDispatcher()
        
        # Check circuit breaker is configured
        breaker = circuit_manager.get_breaker("telegram_dispatcher")
        assert breaker is not None
        
        # Check initial state
        state = breaker.get_state()
        assert state.value in ["closed", "open", "half_open"]
    
    @pytest.mark.asyncio
    async def test_retry_policy_integration(self):
        """Test retry policy integration."""
        from telegram_bot.dispatcher import TelegramDispatcher
        
        dispatcher = TelegramDispatcher()
        
        # Check retry policy is configured
        assert dispatcher._retry_policy is not None
        assert dispatcher._retry_policy.max_attempts == 3


class TestMetricsIntegration:
    """Integration tests for metrics collection."""
    
    @pytest.mark.asyncio
    async def test_classifier_metrics(self):
        """Test intent classifier metrics."""
        from telegram_bot.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        
        # Make some classifications
        await classifier.classify("/start")
        await classifier.classify("search trains")
        await classifier.classify("check pnr")
        
        metrics = classifier.get_metrics()
        
        assert "total_classifications" in metrics
        assert "accuracy" in metrics
        assert metrics["total_classifications"] >= 3
    
    @pytest.mark.asyncio
    async def test_dispatcher_metrics(self):
        """Test dispatcher metrics."""
        from telegram_bot.dispatcher import TelegramDispatcher
        
        dispatcher = TelegramDispatcher()
        
        metrics = dispatcher.get_metrics()
        
        assert "total_operations" in metrics
        assert "success_rate" in metrics
        assert "circuit_breaker" in metrics


# Performance tests
class TestPerformance:
    """Performance and load tests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self):
        """Test handling multiple messages concurrently."""
        from telegram_bot.bot import TelegramBot
        
        bot = TelegramBot()
        
        updates = [
            {
                "update_id": i,
                "message": {
                    "message_id": i,
                    "from": {"id": 123, "first_name": "Test"},
                    "chat": {"id": 123, "type": "private"},
                    "date": 1234567890,
                    "text": "/start"
                }
            }
            for i in range(10)
        ]
        
        with patch.object(bot.dispatcher, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Process all updates concurrently
            tasks = [bot.process_update(update) for update in updates]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should complete without exception
            for result in results:
                if isinstance(result, Exception):
                    pytest.fail(f"Unexpected exception: {result}")
    
    @pytest.mark.asyncio
    async def test_intent_classification_performance(self):
        """Test intent classification performance."""
        import time
        from telegram_bot.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        
        test_inputs = [
            "/start",
            "Search trains from Mumbai to Delhi",
            "Check PNR 1234567890",
            "Book a ticket",
            "What is my booking status",
            "Help me with booking",
            "SOS emergency"
        ]
        
        start = time.time()
        for text in test_inputs:
            await classifier.classify(text)
        elapsed = time.time() - start
        
        # Should process all inputs quickly
        assert elapsed < 5.0  # Less than 5 seconds for 7 classifications


# Run integration tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
