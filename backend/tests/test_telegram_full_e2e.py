import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.base import Base
from database.models import User, TelegramSession, Booking, TelegramAccount
from services.telegram_conversation_engine import ConversationEngine
from api.telegram_bot import start_command_handler, process_telegram_message
from schemas.telegram_bot_schemas import Update, Message, Chat, CallbackQuery

# Setup in-memory SQLite for testing
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    # Create a test user
    user = User(
        id="user_123",
        email="test@example.com",
        full_name="Test User",
        telegram_link_token="LINK123",
        telegram_link_expiry=datetime(2026, 12, 31),
        karma_score=150
    )
    session.add(user)
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_full_telegram_journey(db):
    chat_id = 999
    
    with patch("api.telegram_bot.SessionTransit", return_value=db):
        # 1. TEST LINKING (/start LINK123)
        with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send:
            await start_command_handler(chat_id, "LINK123", db)
            
            # Verify account created
            account = db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
            assert account is not None
            assert account.user_id == "user_123"
            assert "Connection Established" in mock_send.call_args[0][1]

        # Shared user/chat info
        tg_user_dict = {"id": chat_id, "is_bot": False, "first_name": "Test"}
        chat_dict = {"id": chat_id, "type": "private"}
        msg_dict = {
            "message_id": 1,
            "chat": chat_dict,
            "text": "Delhi to Mumbai",
            "date": int(datetime.utcnow().timestamp()),
            "from": tg_user_dict
        }

        # 2. TEST SEARCH FLOW
        with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send, \
             patch("utils.nlp_router.get_local_intent") as mock_nlp, \
             patch("services.unified_travel_planner.UnifiedTravelPlanner.create_travel_plan", new_callable=AsyncMock) as mock_plan:
            
            mock_nlp.return_value = {"intent": "search", "entities": {"source": "DELHI", "destination": "MUMBAI"}}
            
            from services.unified_travel_planner import TravelOption, TravelPlan, TravelRequest
            
            option = TravelOption(
                option_id="opt_456", option_type="direct", from_station="DELHI", to_station="MUMBAI",
                departure_time=datetime.utcnow(), arrival_time=datetime.utcnow(),
                total_duration_minutes=1000, total_fare=500.0, comfort_score=0.9, crowd_level="low", crowd_avoidance_score=0.9
            )
            req = MagicMock(spec=TravelRequest)
            mock_plan.return_value = TravelPlan(plan_id="plan_789", request=req, options=[option])

            update = Update.model_validate({"update_id": 1, "message": msg_dict})
            await process_telegram_message(update)
            
            # Verify session
            session = db.query(TelegramSession).filter(TelegramSession.telegram_id == str(chat_id)).first()
            assert session.current_intent == "search"
            assert "Travel Plan" in mock_send.call_args[0][1]

        # 3. TEST PASSENGER WIZARD
        with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send:
            # Start booking flow
            cb_confirm = {
                "id": "cb_confirm", "from": tg_user_dict, "message": msg_dict,
                "data": "confirm_booking"
            }
            await process_telegram_message(Update.model_validate({"update_id": 2, "callback_query": cb_confirm}))
            assert "Passenger Details" in mock_send.call_args[0][1]

            # Enter passenger info
            msg_pax = msg_dict.copy()
            msg_pax["text"] = "Gaurav Nagar, 25, M"
            await process_telegram_message(Update.model_validate({"update_id": 3, "message": msg_pax}))
            assert "Added Gaurav Nagar" in mock_send.call_args[0][1]

        # 4. TEST LEDGER / TRANSACTIONS
        with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send:
            msg_ledger = msg_dict.copy()
            msg_ledger["text"] = "/transactions"
            await process_telegram_message(Update.model_validate({"update_id": 4, "message": msg_ledger}))
            assert "Financial Ledger" in mock_send.call_args[0][1]
            assert "Karma: 150" in mock_send.call_args[0][1]

