import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.base import Base
from database.models import User, TelegramSession, Booking
from services.telegram_conversation_engine import ConversationEngine


def create_all_safe(metadata, engine):
    try:
        metadata.create_all(bind=engine)
    except OperationalError as exc:
        msg = str(exc).lower()
        if "already exists" in msg and "create unique index" in msg:
            return
        raise

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_all_safe(Base.metadata, engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def conversation_engine(db):
    return ConversationEngine(db)

@pytest.mark.asyncio
async def test_search_flow_start(conversation_engine, db):
    chat_id = 12345
    text = "Delhi to Mumbai"
    
    with patch("utils.nlp_router.get_local_intent") as mock_nlp, \
         patch("services.telegram_dispatcher.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send, \
         patch("services.unified_travel_planner.UnifiedTravelPlanner.create_travel_plan", new_callable=AsyncMock) as mock_plan:
        
        mock_nlp.return_value = {
            "intent": "search",
            "entities": {"source": "DELHI", "destination": "MUMBAI"},
            "confidence": 0.95
        }
        
        # Mock travel option
        from services.unified_travel_planner import TravelOption, TravelPlan, TravelRequest
        option = TravelOption(
            option_id="opt_123",
            option_type="direct",
            from_station="DELHI",
            to_station="MUMBAI",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow(),
            total_duration_minutes=1000,
            total_fare=3000.0,
            comfort_score=0.9,
            crowd_level="low",
            crowd_avoidance_score=0.8
        )
        req = MagicMock(spec=TravelRequest)
        mock_plan.return_value = TravelPlan(plan_id="plan_123", request=req, options=[option])
        
        await conversation_engine.handle_message(chat_id, text)
        
        # Verify session state
        session = db.query(TelegramSession).filter(TelegramSession.telegram_id == str(chat_id)).first()
        assert session.current_intent == "search"
        assert session.current_step == "results"
        
        # Verify message sent
        assert mock_send.called
        args, kwargs = mock_send.call_args
        assert "Travel Plan" in args[1]
        assert "Direct" in args[1]

@pytest.mark.asyncio
async def test_callback_selection(conversation_engine, db):
    chat_id = 12345
    # Pre-create session
    from services.telegram_session_manager import session_manager
    session_manager.update_session(db, str(chat_id), intent="search", step="results", context={"source": "DELHI", "destination": "MUMBAI"})
    
    with patch("services.telegram_dispatcher.telegram_dispatcher.send_message", new_callable=AsyncMock) as mock_send, \
         patch("services.telegram_dispatcher.telegram_dispatcher._api_request", new_callable=AsyncMock) as mock_api:
        
        await conversation_engine.handle_callback(chat_id, "select_train:12951", "callback_query_id")
        
        # Verify session state
        session = db.query(TelegramSession).filter(TelegramSession.telegram_id == str(chat_id)).first()
        assert session.current_intent == "booking"
        assert session.current_step == "confirm"
        assert session.context_data["selected_train"] == "12951"
        
        assert mock_send.called
        assert "confirmed" in mock_send.call_args[0][1].lower()
        assert "12951" in mock_send.call_args[0][1]

