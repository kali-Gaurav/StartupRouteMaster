from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Chat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class User(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None



class Location(BaseModel):
    latitude: float
    longitude: float

class Message(BaseModel):
    message_id: int
    from_user: Optional[User] = Field(alias="from")
    chat: Chat
    date: int
    text: Optional[str] = None
    location: Optional[Location] = None  # Telegram location object
    # Add other fields as needed, e.g., entities, photo, document, etc.

class CallbackQuery(BaseModel):
    id: str
    from_user: User = Field(alias="from")
    message: Optional[Message] = None
    data: Optional[str] = None
    
class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None
    # Add other update types as needed, e.g., edited_message, inline_query, etc.

class TelegramWebhookResponse(BaseModel):
    ok: bool = True
    description: Optional[str] = None