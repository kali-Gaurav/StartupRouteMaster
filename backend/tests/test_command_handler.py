import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.command_handlers.command_handler import CommandHandler

@pytest.fixture
def command_handler_instance():
    """Provides a fresh CommandHandler instance for each test."""
    handler = CommandHandler()
    # Mock the telegram_dispatcher to avoid actual API calls during unit tests
    handler.telegram_dispatcher = AsyncMock() 
    return handler

@pytest.mark.asyncio
async def test_register_and_dispatch_command(command_handler_instance):
    """Test if a registered command is dispatched correctly."""
    mock_handler = AsyncMock()
    command_handler_instance.register_command("/test", mock_handler)

    chat_id = 123
    text = "/test arg1 arg2"
    
    await command_handler_instance.handle_message(chat_id, text, db_session=MagicMock())
    mock_handler.assert_called_once_with(chat_id, "arg1 arg2", db_session=ANY) # ANY will match MagicMock()

@pytest.mark.asyncio
async def test_dispatch_default_handler(command_handler_instance):
    """Test if the default handler is dispatched for unknown commands."""
    mock_default_handler = AsyncMock()
    command_handler_instance.register_default_handler(mock_default_handler)

    chat_id = 456
    text = "some random message"
    
    await command_handler_instance.handle_message(chat_id, text, db_session=MagicMock())
    mock_default_handler.assert_called_once_with(chat_id, text, db_session=ANY)

@pytest.mark.asyncio
async def test_no_handler_and_no_default_handler(command_handler_instance):
    """
    Test behavior when no specific command handler and no default handler are registered.
    Expects a message sent back to the user.
    """
    chat_id = 789
    text = "/unknown_command"
    
    # Mock the _api_request method on the telegram_dispatcher instance
    command_handler_instance.telegram_dispatcher._api_request = AsyncMock()
    
    await command_handler_instance.handle_message(chat_id, text, db_session=MagicMock())
    
    command_handler_instance.telegram_dispatcher._api_request.assert_called_once()
    method_name, payload = command_handler_instance.telegram_dispatcher._api_request.call_args.args
    assert method_name == "sendMessage"
    assert payload["chat_id"] == chat_id
    assert "don't understand that command" in payload["text"]
@pytest.mark.asyncio
async def test_command_without_arguments(command_handler_instance):
    """Test dispatching a command without arguments."""
    mock_handler = AsyncMock()
    command_handler_instance.register_command("/simple", mock_handler)

    chat_id = 101
    text = "/simple"
    
    await command_handler_instance.handle_message(chat_id, text, db_session=MagicMock())
    mock_handler.assert_called_once_with(chat_id, "", db_session=ANY)

@pytest.mark.asyncio
async def test_case_insensitivity_of_command(command_handler_instance):
    """Test if command matching is case-insensitive."""
    mock_handler = AsyncMock()
    command_handler_instance.register_command("/case", mock_handler)

    chat_id = 202
    text = "/CaSe some_args"
    
    await command_handler_instance.handle_message(chat_id, text, db_session=MagicMock())
    mock_handler.assert_called_once_with(chat_id, "some_args", db_session=ANY)

# Helper for testing ANY in calls
from unittest.mock import ANY

