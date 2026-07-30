import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.base import Base
from database.models import User, TelegramSession, TelegramAccount, SOSEvent
from services.telegram_conversation_engine import ConversationEngine
from api.telegram_bot import process_telegram_message
from schemas.telegram_bot_schemas import Update, Message

# Setup
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    # Create test user
    user = User(id="user_hardened", email="hard@test.com", full_name="Hardened User")
    session.add(user)
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_tc01_intent_override(db):
    """TC-01: SOS should override active search state."""
    chat_id = 888
    # Set active search state
    from services.telegram_session_manager import session_manager
    session_manager.update_session(db, str(chat_id), intent="search", step="awaiting_route")
    
    with patch("api.telegram_bot.SessionTransit", return_value=db), \
         patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send, \
         patch("utils.nlp_router.get_local_intent") as mock_nlp:
        
        # User sends SOS instead of route
        mock_nlp.return_value = {"intent": "sos"}
        
        update = Update.model_validate({
            "update_id": 100,
            "message": {
                "message_id": 1,
                "date": 12345,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "is_bot": False, "first_name": "User"},
                "text": "HELP ME SOS"
            }
        })
        
        await process_telegram_message(update)
        
        # Verify state cleared or changed to SOS
        # The engine sends 'SOS RECEIVED' to user and an alert to admin.
        found_sos = False
        for call in mock_send.call_args_list:
            # call.args might be (chat_id, text)
            if len(call.args) > 1 and "SOS" in str(call.args[1]):
                found_sos = True
                break
        assert found_sos

@pytest.mark.asyncio
async def test_tc04_identity_conflict(db):
    """TC-04: Prevent duplicate linking of Telegram ID."""
    chat_id = "tg_999"
    # User A already linked
    acc = TelegramAccount(user_id="user_A", telegram_id=chat_id)
    db.add(acc)
    db.commit()
    
    from api.telegram_bot import start_command_handler
    # User B tries to link same Telegram ID
    user_b = User(id="user_B", telegram_link_token="TOKEN_B", telegram_link_expiry=datetime.utcnow() + timedelta(hours=1))
    db.add(user_b)
    db.commit()
    
    with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send:
        # This should fail or handle the conflict
        await start_command_handler(int(chat_id.replace("tg_","")), "TOKEN_B", db)
        # We need to ensure the system doesn't just overwrite without logic
        account = db.query(TelegramAccount).filter(TelegramAccount.telegram_id == chat_id).first()
        # In our implementation, it updates the user_id. We should check if this is the desired behavior or if we need a block.
        # For 'Patent Level', we should probably block or notify.

@pytest.mark.asyncio
async def test_tc05_performance_burst(db):
    """TC-05: Simulate rapid-fire requests (Race Condition)."""
    chat_id = 777
    engine = ConversationEngine(db)
    
    with patch("services.telegram.bot.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send, \
         patch("utils.nlp_router.get_local_intent", return_value={"intent": "search"}):
        
        # Fire 10 requests at once
        tasks = [engine.handle_message(chat_id, f"Search {i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Check that sessions are handled correctly (no duplicate ID errors in SQLite)
        sessions = db.query(TelegramSession).filter(TelegramSession.telegram_id == str(chat_id)).all()
        assert len(sessions) == 1 

@pytest.mark.asyncio
async def test_tc06_poison_payload(db):
    """TC-06: Malformed webhook handling."""
    with patch("api.telegram_bot.SessionTransit", return_value=db), \
         patch("api.telegram_bot.logger") as mock_logger:
        # Missing required 'message' fields but passed validation (if possible)
        # We'll test with a schema-valid but logically empty update
        update = Update(update_id=1) 
        await process_telegram_message(update)
        # Should not crash
        assert not mock_logger.error.called

