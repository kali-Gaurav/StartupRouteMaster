"""
Telegram Bot Schemas
====================
Pydantic models for request/response handling.
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class UpdateType(str, Enum):
    """Types of Telegram updates."""
    MESSAGE = "message"
    CALLBACK_QUERY = "callback_query"
    EDITED_MESSAGE = "edited_message"
    CHANNEL_POST = "channel_post"
    POLL = "poll"


class MessageType(str, Enum):
    """Types of messages."""
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    VOICE = "voice"
    VIDEO = "video"
    WEB_APP_DATA = "web_app_data"


class UserState(str, Enum):
    """User conversation states."""
    IDLE = "idle"
    SEARCHING = "searching"
    BOOKING = "booking"
    PAYMENT = "payment"
    CANCELLING = "cancelling"
    PROFILE = "profile"
    FEEDBACK = "feedback"
    SOS = "sos"
    AUTH = "auth"
    PNR_INPUT = "pnr_input_flow"
    PROFILE_EDIT = "profile_edit_flow"
    AWAITING_ORIGIN = "awaiting_origin"
    AWAITING_DESTINATION = "awaiting_destination"
    AWAITING_DATE = "awaiting_date"
    READY_TO_SEARCH = "ready_to_search"


class IntentType(str, Enum):
    """User intent types."""
    # Search intents
    SEARCH_TRAINS = "search_trains"
    SEARCH_STATIONS = "search_stations"
    CHECK_AVAILABILITY = "check_availability"
    
    # Booking intents
    BOOK_TICKET = "book_ticket"
    VIEW_BOOKINGS = "view_bookings"
    CANCEL_BOOKING = "cancel_booking"
    DOWNLOAD_TICKET = "download_ticket"
    
    # PNR intents
    CHECK_PNR = "check_pnr"
    TRACK_PNR = "track_pnr"
    
    # Status intents
    TRAIN_STATUS = "train_status"
    STATION_DEPARTURES = "station_departures"
    DELAY_INFO = "delay_info"
    
    # User intents
    MY_PROFILE = "my_profile"
    UPDATE_PROFILE = "update_profile"
    MY_WALLET = "my_wallet"
    
    # Help intents
    HELP = "help"
    SUPPORT = "support"
    
    # SOS intents
    SOS_EMERGENCY = "sos_emergency"
    SAFETY_STATUS = "safety_status"
    
    # Navigation
    START = "start"
    BACK = "back"
    MAIN_MENU = "main_menu"
    
    # Flow related
    FLOW_CANCEL = "flow_cancel"
    FLOW_NEXT = "flow_next"
    
    # Unknown
    UNKNOWN = "unknown"


# Request Schemas
class TelegramUser(BaseModel):
    """Telegram user information."""
    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat information."""
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(BaseModel):
    """Telegram message."""
    message_id: int
    from_user: Optional[TelegramUser] = None
    chat: TelegramChat
    date: datetime
    text: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    location: Optional[Dict[str, float]] = None
    contact: Optional[Dict[str, str]] = None
    web_app_data: Optional[Dict[str, str]] = None
    reply_to_message: Optional["TelegramMessage"] = None


class CallbackQuery(BaseModel):
    """Callback query from inline keyboard."""
    id: str
    from_user: TelegramUser
    message: Optional[TelegramMessage] = None
    data: str


class TelegramUpdate(BaseModel):
    """Telegram update wrapper."""
    update_id: int
    update_type: UpdateType
    message: Optional[TelegramMessage] = None
    callback_query: Optional[CallbackQuery] = None
    edited_message: Optional[TelegramMessage] = None


# Context Schemas
class UserContext(BaseModel):
    """User conversation context."""
    chat_id: int
    user_id: int
    state: UserState = UserState.IDLE
    intent: Optional[IntentType] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationStep(BaseModel):
    """Multi-step conversation step."""
    step_id: str
    intent: IntentType
    step_number: int
    total_steps: int
    data: Dict[str, Any] = Field(default_factory=dict)
    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)


# Response Schemas
class BotResponse(BaseModel):
    """Bot response to user."""
    chat_id: int
    text: str
    parse_mode: str = "HTML"
    keyboard: Optional[Dict[str, Any]] = None
    inline_keyboard: Optional[List[List[Dict[str, str]]]] = None
    reply_to: Optional[int] = None
    delete_after: Optional[int] = None


class SearchRequest(BaseModel):
    """Train search request."""
    from_station: str
    to_station: str
    date: str  # YYYY-MM-DD
    class_type: Optional[str] = None
    quota: Optional[str] = None
    passengers: int = 1


class BookingRequest(BaseModel):
    """Booking request."""
    train_no: str
    from_station: str
    to_station: str
    date: str
    class_type: str
    quota: str
    passengers: List[Dict[str, Any]]
    contact_phone: str
    contact_email: Optional[str] = None


class PNRCheckRequest(BaseModel):
    """PNR check request."""
    pnr_number: str


# Analytics Schemas
class UserAction(BaseModel):
    """User action for analytics."""
    user_id: int
    chat_id: int
    intent: IntentType
    action: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Update forward references
TelegramMessage.model_rebuild()
TelegramUpdate.model_rebuild()
