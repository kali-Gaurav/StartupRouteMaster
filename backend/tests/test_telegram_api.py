import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from unittest.mock import AsyncMock, patch, MagicMock

# Import the router where telegram_webhook is defined
from api.telegram_bot import router as telegram_router
from backend.schemas.telegram_bot_schemas import Update, Message, Chat, User
from backend.services.command_handlers.command_handler import CommandHandler
from backend.services.telegram_dispatcher import TelegramDispatcher
import api.telegram_bot as telegram_module

# Create a test FastAPI app
app = FastAPI()
app.include_router(telegram_router)

# Mock external dependencies
@pytest.fixture(autouse=True)
def mock_dependencies():
    mock_get_db = MagicMock()
    mock_get_current_user = MagicMock()

    def fake_get_db():
        yield mock_get_db()

    def fake_get_current_user():
        return mock_get_current_user()

    with (\
        patch('api.telegram_bot.SessionTransit') as mock_session_transit,\
        patch('backend.api.telegram_bot.SessionTransit', mock_session_transit),\
        patch('api.telegram_bot.command_handler', spec=CommandHandler) as mock_command_handler,\
        patch('backend.api.telegram_bot.command_handler', mock_command_handler),\
        patch('api.telegram_bot.telegram_dispatcher', spec=TelegramDispatcher) as mock_telegram_dispatcher,\
        patch('backend.api.telegram_bot.telegram_dispatcher', mock_telegram_dispatcher)\
    ):
        
        mock_session_transit.return_value = MagicMock()
        mock_session_transit.return_value.close = MagicMock()

        mock_telegram_dispatcher._api_request = AsyncMock()
        mock_telegram_dispatcher.send_welcome = AsyncMock()
        mock_telegram_dispatcher.get_keyboard = MagicMock(return_value={})

        app.dependency_overrides[telegram_module.get_db] = fake_get_db
        app.dependency_overrides[telegram_module.get_current_user] = fake_get_current_user

        yield {
            "session_transit": mock_session_transit,
            "command_handler": mock_command_handler,
            "telegram_dispatcher": mock_telegram_dispatcher,
            "get_db": mock_get_db,
            "get_current_user": mock_get_current_user
        }

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_telegram_webhook_valid_message(mock_dependencies):
    """
    Test a valid incoming Telegram message via webhook.
    Verifies processing is passed to command_handler.
    """
    mock_command_handler = mock_dependencies["command_handler"]
    mock_command_handler.handle_message = AsyncMock()

    test_update = {
        "update_id": 12345,
        "message": {
            "message_id": 1,
            "from": {"id": 101, "is_bot": False, "first_name": "Test", "username": "testuser"},
            "chat": {"id": 789, "type": "private"},
            "date": 1678886400,
            "text": "/start"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/telegram/webhook", json=test_update)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    await asyncio.sleep(0.1)
    mock_command_handler.handle_message.assert_called_once()
    args, kwargs = mock_command_handler.handle_message.call_args
    assert args[0] == 789
    assert args[1] == "/start"
    assert "db_session" in kwargs


@pytest.mark.asyncio
async def test_telegram_webhook_invalid_message():
    """
    Test an invalid incoming Telegram message via webhook.
    Verifies FastAPI's Pydantic validation returns a 422 error.
    """
    invalid_update_payload = {
        "update_id": 12346,
        "message": {
            "message_id": "not_an_int",
            "from": {"id": 102, "is_bot": False},
            "chat": {"id": 790, "type": "private"},
            "date": 1678886401,
            "text": "/help"
        }
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/telegram/webhook", json=invalid_update_payload)

    assert response.status_code == 422
    assert "valid integer" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_generate_link_token(mock_dependencies):
    mock_user = MagicMock()
    mock_user.telegram_link_token = None
    mock_user.telegram_link_expiry = None
    mock_dependencies["get_current_user"].return_value = mock_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/telegram/link-token")

    assert response.status_code == 200
    payload = response.json()
    assert "token" in payload
    assert payload["expires_in"] == 600
    assert mock_user.telegram_link_token is not None
    assert mock_user.telegram_link_expiry is not None


@pytest.mark.asyncio
async def test_link_telegram_endpoint_conflict(mock_dependencies):
    existing_user = MagicMock()
    existing_user.id = "other-user"
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_user
    mock_dependencies["get_db"].return_value = mock_db

    mock_current_user = MagicMock()
    mock_current_user.id = "current-user"
    mock_dependencies["get_current_user"].return_value = mock_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/telegram/link", params={"telegram_id": "12345"})

    assert response.status_code == 400
    assert response.json()["detail"] == "This Telegram account is already linked to another user."


@pytest.mark.asyncio
async def test_search_command_handler_calls_search(monkeypatch, mock_dependencies):
    from backend.api.telegram_bot import search_command_handler

    mock_db = MagicMock()
    mock_service = MagicMock()
    mock_service.search_routes = AsyncMock(return_value={"journeys": [{
        "train_name": "Test Express",
        "departure_time": "10:00",
        "arrival_time": "18:00",
        "available_seats": 10,
        "fare": "₹500"
    }]})
    monkeypatch.setattr('backend.api.telegram_bot.SearchService', lambda db: mock_service)

    await search_command_handler(12345, "Mumbai to Delhi on 2026-05-01", mock_db)
    mock_dependencies["telegram_dispatcher"].send_message.assert_called_once()


@pytest.mark.asyncio
async def test_pnr_command_handler_found_booking(monkeypatch, mock_dependencies):
    from backend.api.telegram_bot import pnr_command_handler

    mock_booking = MagicMock()
    mock_booking.pnr_number = "1234567890"
    mock_booking.booking_details = {"train_name": "Test Express", "from": "Mumbai", "to": "Delhi"}
    mock_booking.travel_date = "2026-05-01"
    mock_booking.booking_status = "CONFIRMED"
    mock_booking.amount_paid = 550.0

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_booking

    await pnr_command_handler(12345, "1234567890", mock_db)
    mock_dependencies["telegram_dispatcher"].send_message.assert_called_once()
