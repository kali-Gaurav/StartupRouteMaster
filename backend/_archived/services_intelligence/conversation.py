"""
Conversation Manager
====================

Manages multi-turn conversations with state tracking and context awareness.
Handles user intents, entities extraction, and conversation flow.

Author: RouteMaster Team
Version: 1.0.0
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import uuid
import re

from .response_types import (
    InteractiveResponse, ResponseType, ActionType, Button, CarouselItem
)

logger = logging.getLogger("conversation.manager")


class Intent(str, Enum):
    """User intents"""
    SEARCH_TRAINS = "search_trains"
    CHECK_PNR = "check_pnr"
    TRACK_TRAIN = "track_train"
    BOOK_TICKET = "book_ticket"
    CANCEL_BOOKING = "cancel_booking"
    RESCHEDULE = "reschedule"
    VIEW_BOOKINGS = "view_bookings"
    GET_AMENITIES = "get_amenities"
    BOOK_WAITING = "book_waiting"
    REDEEM_VOUCHER = "redeem_voucher"
    REQUEST_REFUND = "request_refund"
    RATE_JOURNEY = "rate_journey"
    REPORT_ISSUE = "report_issue"
    EMERGENCY_SOS = "emergency_sos"
    GET_HELP = "get_help"
    VIEW_DASHBOARD = "view_dashboard"
    SHARE_ITINERARY = "share_itinerary"
    DOWNLOAD_TICKET = "download_ticket"
    ADD_TO_CALENDAR = "add_to_calendar"
    CHECK_AVAILABILITY = "check_availability"
    GET_CROWD_INFO = "get_crowd_info"
    INITIATE_REDISTRIBUTION = "initiate_redistribution"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    THANK_YOU = "thank_you"
    UNKNOWN = "unknown"


class ConversationState(str, Enum):
    """Conversation states"""
    IDLE = "idle"
    COLLECTING_SEARCH_PARAMS = "collecting_search_params"
    COLLECTING_BOOKING_DETAILS = "collecting_booking_details"
    CONFIRMING_BOOKING = "confirming_booking"
    PROCESSING_PAYMENT = "processing_payment"
    COLLECTING_FEEDBACK = "collecting_feedback"
    HANDLING_EMERGENCY = "handling_emergency"
    COLLECTING_ISSUE_REPORT = "collecting_issue_report"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"


@dataclass
class Entity:
    """Extracted entity from user message"""
    entity_type: str
    value: Any
    confidence: float
    start_pos: int
    end_pos: int
    
    def __hash__(self):
        return hash((self.entity_type, self.value))
    
    def __eq__(self, other):
        return self.entity_type == other.entity_type and self.value == other.value


@dataclass
class ConversationContext:
    """Conversation context and state"""
    conversation_id: str
    user_id: str
    state: ConversationState
    intent: Intent
    entities: Dict[str, Any]
    entities_list: List[Entity]
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_interaction: datetime
    expires_at: datetime
    
    def __post_init__(self):
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())
    
    def add_entity(self, entity: Entity):
        """Add entity to context"""
        self.entities[entity.entity_type] = entity.value
        self.entities_list.append(entity)
        self.updated_at = datetime.utcnow()
        self.last_interaction = datetime.utcnow()
    
    def add_to_history(self, role: str, message: str, response: Optional[InteractiveResponse] = None):
        """Add to conversation history"""
        entry = {
            "role": role,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        if response:
            entry["response_type"] = response.response_type.value
            entry["response_id"] = response.response_id
        self.history.append(entry)
        self.last_interaction = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if conversation is expired"""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "intent": self.intent.value,
            "entities": self.entities,
            "history_count": len(self.history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_interaction": self.last_interaction.isoformat()
        }


class ConversationManager:
    """
    Manages multi-turn conversations with state tracking and context awareness.
    """
    
    # Conversation timeout (30 minutes)
    CONVERSATION_TIMEOUT = timedelta(minutes=30)
    
    # Intent patterns for NLU
    INTENT_PATTERNS = {
        Intent.SEARCH_TRAINS: [
            r"(search|find|look for|show me|get).*(train|route|journey)",
            r"(train|route|journey).*(from|between).*(to|and)",
            r"^(NDLS|BCT|ADI|BSB|CDG|DDNC|DLI|GKP|HWH|JP|LKO|MCT|MYS|NDLS|NJP|PUNE|SBC|SHM|SHM|SVDK|YNK)$",
            r"(check|show|find).*(availability|seat)",
            r"next train",
            r"train schedule"
        ],
        Intent.CHECK_PNR: [
            r"(check|status|track).*pnr",
            r"pnr.*(status|check)",
            r"booking status",
            r"ticket status"
        ],
        Intent.TRACK_TRAIN: [
            r"(track|live|status|where is).*train",
            r"train.*(location|position|status)",
            r"live.*(train|status)",
            r"running status"
        ],
        Intent.BOOK_TICKET: [
            r"(book|reserve|order|purchase).*(ticket|seat|berth)",
            r"book.*train",
            r"reserve.*(from|to)",
            r"buy.*ticket"
        ],
        Intent.CANCEL_BOOKING: [
            r"(cancel|abort|revoke).*(booking|ticket|reservation)",
            r"cancel.*pnr",
            r"get.*refund"
        ],
        Intent.RESCHEDULE: [
            r"(reschedule|change|modify|update).*(booking|ticket|date)",
            r"change.*train",
            r"different.*date"
        ],
        Intent.VIEW_BOOKINGS: [
            r"(my|show|view|list).*(booking|booking|ticket|tickets)",
            r"past.*journey",
            r"booking.*history"
        ],
        Intent.GET_AMENITIES: [
            r"(amenities|facilities|services|available).*(at|station)",
            r"station.*(amenities|facilities)",
            r"what.*available.*station"
        ],
        Intent.BOOK_WAITING: [
            r"(book|reserve).*(waiting|lounge|waiting room)",
            r"waiting.*(lounge|room)",
            r"station.*lounge"
        ],
        Intent.EMERGENCY_SOS: [
            r"(emergency|sos|help|accident|incident|unsafe)",
            r"not.*safe",
            r"need.*help",
            r"call.*police",
            r"medical.*help"
        ],
        Intent.GREETING: [
            r"^(hi|hello|hey|good morning|good afternoon|good evening|namaste)",
            r"start",
            r"how are you"
        ],
        Intent.GOODBYE: [
            r"(bye|goodbye|see you|tata|ciao|stop|end)",
            r"that's all"
        ],
        Intent.THANK_YOU: [
            r"(thanks|thank you|thx|ty|appreciate)"
        ],
        Intent.GET_HELP: [
            r"(help|support|assist|guide|what can you do)",
            r"how.*work",
            r"commands|options|features",
            r"need help",
            r"i need help"
        ],
        Intent.VIEW_DASHBOARD: [
            r"(dashboard|profile|account|settings)",
            r"open.*web",
            r"website"
        ]
    }
    
    # Station code patterns
    STATION_PATTERN = re.compile(
        r'\b(NDLS|BCT|ADI|BSB|CDG|DDNC|DLI|GKP|HWH|JP|LKO|MCT|MYS|NJP|PUNE|SBC|SHM|SVDK|YNK|BLR|MAA|KOL|HYD|BOM|DEL)\b',
        re.IGNORECASE
    )
    
    # Date patterns
    DATE_PATTERN = re.compile(
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|'
        r'(today|tomorrow|day after tomorrow)|'
        r'(\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*,?\s*\d{2,4})',
        re.IGNORECASE
    )
    
    # PNR pattern
    PNR_PATTERN = re.compile(r'\b(\d{10})\b')
    
    # Train number pattern
    TRAIN_PATTERN = re.compile(r'\b(\d{4,5})\b')
    
    def __init__(self, max_history: int = 20):
        self._conversations: Dict[str, ConversationContext] = {}
        self._user_sessions: Dict[str, str] = {}  # user_id -> conversation_id
        self._handlers: Dict[Intent, Callable] = {}
        self._default_handler: Optional[Callable] = None
        self._max_history = max_history
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = datetime.utcnow()
        
        logger.info("ConversationManager initialized")
    
    def register_handler(self, intent: Intent, handler: Callable):
        """Register a handler for an intent"""
        self._handlers[intent] = handler
        logger.debug(f"Registered handler for intent: {intent.value}")
    
    def set_default_handler(self, handler: Callable):
        """Set default handler for unknown intents"""
        self._default_handler = handler
    
    def get_or_create_conversation(
        self,
        user_id: str,
        platform: str = "telegram"
    ) -> ConversationContext:
        """Get existing conversation or create new one"""
        # Check for existing active conversation
        if user_id in self._user_sessions:
            conv_id = self._user_sessions[user_id]
            if conv_id in self._conversations:
                conv = self._conversations[conv_id]
                if not conv.is_expired():
                    return conv
        
        # Create new conversation
        conv_id = str(uuid.uuid4())
        conv = ConversationContext(
            conversation_id=conv_id,
            user_id=user_id,
            state=ConversationState.IDLE,
            intent=Intent.UNKNOWN,
            entities={},
            entities_list=[],
            history=[],
            metadata={"platform": platform},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_interaction=datetime.utcnow(),
            expires_at=datetime.utcnow() + self.CONVERSATION_TIMEOUT
        )
        
        self._conversations[conv_id] = conv
        self._user_sessions[user_id] = conv_id
        
        # Cleanup old conversations
        self._cleanup_expired()
        
        return conv
    
    def extract_entities(self, message: str) -> List[Entity]:
        """Extract entities from user message"""
        entities = []
        
        # Extract station codes
        for match in self.STATION_PATTERN.finditer(message):
            entities.append(Entity(
                entity_type="station_code",
                value=match.group(1).upper(),
                confidence=0.95,
                start_pos=match.start(),
                end_pos=match.end()
            ))
        
        # Extract dates
        for match in self.DATE_PATTERN.finditer(message):
            date_str = match.group(0)
            entities.append(Entity(
                entity_type="date",
                value=date_str,
                confidence=0.85,
                start_pos=match.start(),
                end_pos=match.end()
            ))
        
        # Extract PNR
        for match in self.PNR_PATTERN.finditer(message):
            entities.append(Entity(
                entity_type="pnr",
                value=match.group(1),
                confidence=0.95,
                start_pos=match.start(),
                end_pos=match.end()
            ))
        
        # Extract train numbers
        for match in self.TRAIN_PATTERN.finditer(message):
            # Make sure it's not a PNR (PNR is 10 digits)
            if len(match.group(1)) <= 5:
                entities.append(Entity(
                    entity_type="train_number",
                    value=match.group(1),
                    confidence=0.90,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        # Extract passenger count
        count_match = re.search(r'(\d+)\s*(passenger|person|people|traveller|adult)', message, re.IGNORECASE)
        if count_match:
            entities.append(Entity(
                entity_type="passenger_count",
                value=int(count_match.group(1)),
                confidence=0.85,
                start_pos=count_match.start(),
                end_pos=count_match.end()
            ))
        
        # Extract class preference
        class_match = re.search(r'(SL|3A|2A|1A|CC|EC|FC)\s*(class|ac|sleeper)', message, re.IGNORECASE)
        if class_match:
            entities.append(Entity(
                entity_type="class_preference",
                value=class_match.group(1).upper(),
                confidence=0.90,
                start_pos=class_match.start(),
                end_pos=class_match.end()
            ))
        
        return entities
    
    def detect_intent(self, message: str) -> Intent:
        """Detect user intent from message"""
        message_lower = message.lower()
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.debug(f"Detected intent: {intent.value} for message: {message[:50]}...")
                    return intent
        
        return Intent.UNKNOWN
    
    def process_message(
        self,
        user_id: str,
        message: str,
        platform: str = "telegram",
        context: Optional[ConversationContext] = None
    ) -> InteractiveResponse:
        """
        Process a user message and return an interactive response.
        
        Args:
            user_id: User identifier
            message: User message
            platform: Platform (telegram, web, etc.)
            context: Existing conversation context
            
        Returns:
            InteractiveResponse
        """
        # Get or create conversation
        conv = context or self.get_or_create_conversation(user_id, platform)
        
        # Extract entities
        entities = self.extract_entities(message)
        for entity in entities:
            conv.add_entity(entity)
        
        # Detect intent
        intent = self.detect_intent(message)
        
        # Handle state-specific logic
        response = self._handle_stateful_intent(conv, intent, message)
        
        if response:
            conv.add_to_history("user", message, response)
            conv.intent = intent
            return response
        
        # Use registered handler
        handler = self._handlers.get(intent, self._default_handler)
        if handler:
            response = handler(conv, message)
            if response:
                conv.add_to_history("user", message, response)
                conv.intent = intent
                return response
        
        # Fallback to default response
        response = self._get_fallback_response(conv, intent, message)
        conv.add_to_history("user", message, response)
        conv.intent = intent
        
        return response
    
    def _handle_stateful_intent(
        self,
        conv: ConversationContext,
        intent: Intent,
        message: str
    ) -> Optional[InteractiveResponse]:
        """Handle intent based on current conversation state"""
        
        # If in IDLE state, transition to appropriate state
        if conv.state == ConversationState.IDLE:
            if intent == Intent.SEARCH_TRAINS:
                if self._has_required_entities(conv, ['from_station', 'to_station', 'date']):
                    conv.state = ConversationState.COLLECTING_SEARCH_PARAMS
                    return self._generate_search_results(conv)
                else:
                    conv.state = ConversationState.COLLECTING_SEARCH_PARAMS
                    return self._request_search_params(conv)
            
            elif intent == Intent.BOOK_TICKET:
                conv.state = ConversationState.COLLECTING_BOOKING_DETAILS
                return self._request_booking_details(conv)
            
            elif intent == Intent.CHECK_PNR:
                if conv.entities.get('pnr'):
                    return self._check_pnr_status(conv)
                else:
                    return self._request_pnr(conv)
            
            elif intent == Intent.TRACK_TRAIN:
                if conv.entities.get('train_number'):
                    return self._track_train(conv)
                else:
                    return self._request_train_number(conv)
            
            elif intent == Intent.EMERGENCY_SOS:
                conv.state = ConversationState.HANDLING_EMERGENCY
                return self._generate_sos_response(conv)
            
            elif intent == Intent.GREETING:
                return self._generate_greeting_response(conv)
            
            elif intent == Intent.GET_HELP:
                return self._generate_help_response(conv)
        
        # Handle state-specific continuations
        elif conv.state == ConversationState.COLLECTING_SEARCH_PARAMS:
            if intent == Intent.SEARCH_TRAINS or self._has_required_entities(conv, ['from_station', 'to_station', 'date']):
                return self._generate_search_results(conv)
        
        elif conv.state == ConversationState.COLLECTING_BOOKING_DETAILS:
            if intent == Intent.BOOK_TICKET:
                return self._generate_booking_confirmation(conv)
        
        elif conv.state == ConversationState.HANDLING_EMERGENCY:
            if intent == Intent.EMERGENCY_SOS:
                return self._generate_sos_response(conv)
        
        return None
    
    def _has_required_entities(self, conv: ConversationContext, required: List[str]) -> bool:
        """Check if conversation has required entities"""
        return all(conv.entities.get(e) for e in required)
    
    def _request_search_params(self, conv: ConversationContext) -> InteractiveResponse:
        """Request missing search parameters"""
        missing = []
        if not conv.entities.get('from_station'):
            missing.append("origin station")
        if not conv.entities.get('to_station'):
            missing.append("destination station")
        if not conv.entities.get('date'):
            missing.append("travel date")
        
        missing_text = ", ".join(missing)
        
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        buttons = [
            Button(text="🔍 Quick Search", action="quick_search", style="primary"),
            Button(text="📋 Show All Options", action="show_all_options", style="default")
        ]
        
        return (InteractiveResponseBuilder()
            .buttons(
                content=f"Please provide the following information:\n\n• {missing_text}\n\nOr use the quick search buttons below:",
                buttons=buttons,
                title="Search Trains"
            )
            .build())
    
    def _generate_search_results(self, conv: ConversationContext) -> InteractiveResponse:
        """Generate search results (placeholder - would call actual search service)"""
        from .interactive_response_types import InteractiveResponseBuilder, CarouselItem, Button
        
        # Mock data - in production, this would call the actual search service
        mock_trains = [
            {
                "train_number": "12952",
                "train_name": "Rajdhani Express",
                "from": conv.entities.get('from_station', 'NDLS'),
                "to": conv.entities.get('to_station', 'BCT'),
                "departure_time": "16:00",
                "arrival_time": "22:15",
                "duration": "6h 15m",
                "classes": [
                    {"class_code": "3A", "fare": 1250, "available": True},
                    {"class_code": "2A", "fare": 1850, "available": True},
                    {"class_code": "1A", "fare": 3500, "available": False}
                ]
            },
            {
                "train_number": "12010",
                "train_name": "Shatabdi Express",
                "from": conv.entities.get('from_station', 'NDLS'),
                "to": conv.entities.get('to_station', 'BCT'),
                "departure_time": "06:00",
                "arrival_time": "11:45",
                "duration": "5h 45m",
                "classes": [
                    {"class_code": "CC", "fare": 1100, "available": True},
                    {"class_code": "EC", "fare": 2000, "available": True}
                ]
            }
        ]
        
        items = []
        for train in mock_trains:
            class_buttons = [
                Button(
                    text=f"{cls['class_code']} - ₹{cls['fare']}",
                    action=f"book_{cls['class_code'].lower()}",
                    value=cls['class_code'],
                    style="primary" if cls['available'] else "default"
                )
                for cls in train['classes'][:3]
            ]
            
            item = CarouselItem(
                item_id=train['train_number'],
                title=f"🚂 {train['train_name']}",
                subtitle=f"{train['from']} → {train['to']}",
                description=f"⏰ {train['departure_time']} - {train['arrival_time']} | ⏱️ {train['duration']}",
                buttons=class_buttons,
                metadata=train
            )
            items.append(item)
        
        return (InteractiveResponseBuilder()
            .carousel(
                items=items,
                title=f"Trains: {conv.entities.get('from_station', '')} → {conv.entities.get('to_station', '')}",
                content=f"Showing trains for {conv.entities.get('date', 'today')}"
            )
            .build())
    
    def _request_pnr(self, conv: ConversationContext) -> InteractiveResponse:
        """Request PNR number"""
        from .interactive_response_types import InteractiveResponseBuilder, FormField
        
        return (InteractiveResponseBuilder()
            .form(
                content="Please enter your 10-digit PNR number to check the status.",
                fields=[
                    FormField(
                        field_id="pnr",
                        field_type="text",
                        label="PNR Number",
                        required=True,
                        placeholder="Enter 10-digit PNR",
                        validation={"pattern": r"^\d{10}$", "message": "Please enter a valid 10-digit PNR"}
                    )
                ],
                action=ActionType.CHECK_PNR
            )
            .build())
    
    def _check_pnr_status(self, conv: ConversationContext) -> InteractiveResponse:
        """Check PNR status (placeholder)"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        pnr = conv.entities.get('pnr', '1234567890')
        
        content = f"""
✅ <b>PNR Status: CONFIRMED</b>

🎫 PNR: <code>{pnr}</code>
🚂 Train: Rajdhani Express (12952)
📍 NDLS → BCT
📅 25 Dec 2024
🪑 3AC - Side Lower Berth
        """
        
        buttons = [
            Button(text="🔍 Track Live", action="track_train", style="primary"),
            Button(text="📅 Add to Calendar", action="add_to_calendar", style="default"),
            Button(text="📤 Share", action="share_itinerary", style="default")
        ]
        
        return (InteractiveResponseBuilder()
            .card(
                title="PNR Status",
                content=content,
                buttons=buttons
            )
            .build())
    
    def _request_train_number(self, conv: ConversationContext) -> InteractiveResponse:
        """Request train number"""
        from .interactive_response_types import InteractiveResponseBuilder, FormField
        
        return (InteractiveResponseBuilder()
            .form(
                content="Please enter the train number to track.",
                fields=[
                    FormField(
                        field_id="train_number",
                        field_type="text",
                        label="Train Number",
                        required=True,
                        placeholder="Enter 4-5 digit train number"
                    )
                ],
                action=ActionType.TRACK_TRAIN
            )
            .build())
    
    def _track_train(self, conv: ConversationContext) -> InteractiveResponse:
        """Track train (placeholder)"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        train_num = conv.entities.get('train_number', '12952')
        
        content = f"""
🚂 <b>Live Train Tracking</b>

{train_num} - Rajdhani Express

📍 <b>Current Location:</b> Vadodara (BRC)
⏰ <b>Last Update:</b> 2 minutes ago

📊 <b>Delay:</b> 5 minutes
📈 <b>Speed:</b> 110 km/h

🛤️ <b>Next Stop:</b> Mumbai Central (BCT) - 45 minutes
        """
        
        buttons = [
            Button(text="🔄 Refresh", action="refresh_tracking", style="primary"),
            Button(text="📍 View on Map", action="view_map", style="default"),
            Button(text="👥 Crowd Info", action="crowd_info", style="default")
        ]
        
        return (InteractiveResponseBuilder()
            .card(
                title="Live Train Status",
                content=content,
                buttons=buttons
            )
            .build())
    
    def _request_booking_details(self, conv: ConversationContext) -> InteractiveResponse:
        """Request booking details"""
        from .interactive_response_types import InteractiveResponseBuilder, FormField
        
        return (InteractiveResponseBuilder()
            .form(
                content="Please provide booking details:",
                fields=[
                    FormField(
                        field_id="from_station",
                        field_type="text",
                        label="From Station",
                        required=True,
                        placeholder="e.g., NDLS"
                    ),
                    FormField(
                        field_id="to_station",
                        field_type="text",
                        label="To Station",
                        required=True,
                        placeholder="e.g., BCT"
                    ),
                    FormField(
                        field_id="date",
                        field_type="date",
                        label="Travel Date",
                        required=True
                    ),
                    FormField(
                        field_id="class",
                        field_type="dropdown",
                        label="Class",
                        required=True,
                        options=[
                            {"value": "SL", "label": "Sleeper (SL)"},
                            {"value": "3A", "label": "AC 3-Tier (3A)"},
                            {"value": "2A", "label": "AC 2-Tier (2A)"},
                            {"value": "1A", "label": "AC First Class (1A)"},
                            {"value": "CC", "label": "AC Chair Car (CC)"}
                        ]
                    ),
                    FormField(
                        field_id="passengers",
                        field_type="number",
                        label="Number of Passengers",
                        required=True,
                        default_value=1
                    )
                ],
                action=ActionType.BOOK_TICKET
            )
            .build())
    
    def _generate_booking_confirmation(self, conv: ConversationContext) -> InteractiveResponse:
        """Generate booking confirmation"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        content = f"""
✅ <b>Booking Confirmed!</b>

🎫 PNR: <code>2815473690</code>
🚂 Train: Rajdhani Express (12952)
📍 From: {conv.entities.get('from_station', 'NDLS')}
📍 To: {conv.entities.get('to_station', 'BCT')}
📅 Date: {conv.entities.get('date', '25 Dec 2024')}
🪑 Class: {conv.entities.get('class', '3A')}
💰 Fare: ₹{conv.entities.get('fare', '1250')}
        """
        
        buttons = [
            Button(text="📥 Download Ticket", action="download_ticket", style="primary"),
            Button(text="📅 Add to Calendar", action="add_to_calendar", style="default"),
            Button(text="🔍 Track Live", action="track_train", style="default")
        ]
        
        return (InteractiveResponseBuilder()
            .card(
                title="Booking Confirmed!",
                content=content,
                buttons=buttons
            )
            .build())
    
    def _generate_sos_response(self, conv: ConversationContext) -> InteractiveResponse:
        """Generate SOS emergency response"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        buttons = [
            Button(text="🚨 Call Emergency", action="call_emergency", style="danger"),
            Button(text="📞 Contact Railway", action="contact_railway", style="danger"),
            Button(text="🏥 Medical Help", action="medical_help", style="danger"),
            Button(text="👮 Police", action="police_help", style="danger"),
            Button(text="❌ Cancel", action="cancel_sos", style="default")
        ]
        
        content = "🚨 <b>EMERGENCY SERVICES</b>\n\nSelect an emergency service:"
        
        return (InteractiveResponseBuilder()
            .buttons(
                content=content,
                buttons=buttons,
                title="Emergency Assistance"
            )
            .build())
    
    def _generate_greeting_response(self, conv: ConversationContext) -> InteractiveResponse:
        """Generate greeting response"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        buttons = [
            Button(text="🔍 Search Trains", action="search_trains", style="primary"),
            Button(text="📋 My Bookings", action="my_bookings", style="default"),
            Button(text="🎫 Check PNR", action="check_pnr", style="default"),
            Button(text="🚨 Emergency SOS", action="sos", style="danger")
        ]
        
        content = """
<b>👋 Welcome to RouteMaster!</b>

Your intelligent travel companion for safer and smarter journeys.

How can I help you today?

• 🔍 Search for trains
• 🎫 Check booking status
• 📍 Track your train live
• 📋 View your bookings
• 🚨 Emergency assistance
        """
        
        return (InteractiveResponseBuilder()
            .buttons(
                content=content,
                buttons=buttons,
                title="Welcome!"
            )
            .build())
    
    def _generate_help_response(self, conv: ConversationContext) -> InteractiveResponse:
        """Generate help response"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        buttons = [
            Button(text="🔍 Search Trains", action="search_trains", style="primary"),
            Button(text="📋 How to Book", action="how_to_book", style="default"),
            Button(text="💳 Payment Options", action="payment_info", style="default"),
            Button(text="📞 Contact Support", action="contact_support", style="default")
        ]
        
        content = """
<b>🆘 Help & Support</b>

RouteMaster helps you with:
• 🚂 Train search & booking
• 📍 Live train tracking
• 🎫 PNR status checking
• 📋 Booking management
• 🛋️ Waiting lounge booking
• 🚨 Emergency assistance

What would you like to know more about?
        """
        
        return (InteractiveResponseBuilder()
            .buttons(
                content=content,
                buttons=buttons,
                title="Help Center"
            )
            .build())
    
    def _get_fallback_response(
        self,
        conv: ConversationContext,
        intent: Intent,
        message: str
    ) -> InteractiveResponse:
        """Get fallback response for unknown intents"""
        from .interactive_response_types import InteractiveResponseBuilder, Button
        
        buttons = [
            Button(text="🔍 Search Trains", action="search_trains", style="primary"),
            Button(text="🎫 Check PNR", action="check_pnr", style="default"),
            Button(text="📋 My Bookings", action="my_bookings", style="default"),
            Button(text="🆘 Get Help", action="help", style="default")
        ]
        
        return (InteractiveResponseBuilder()
            .buttons(
                content=f"I didn't understand that. Here's what I can help you with:\n\n{message}",
                buttons=buttons,
                title="How can I help?"
            )
            .build())
    
    def _cleanup_expired(self):
        """Remove expired conversations"""
        now = datetime.utcnow()
        if (now - self._last_cleanup).seconds < self._cleanup_interval:
            return
        
        expired = [
            conv_id for conv_id, conv in self._conversations.items()
            if conv.is_expired()
        ]
        
        for conv_id in expired:
            conv = self._conversations.pop(conv_id)
            if conv.user_id in self._user_sessions:
                del self._user_sessions[conv.user_id]
        
        self._last_cleanup = now
        logger.info(f"Cleaned up {len(expired)} expired conversations")
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation by ID"""
        return self._conversations.get(conversation_id)
    
    def get_user_conversation(self, user_id: str) -> Optional[ConversationContext]:
        """Get active conversation for user"""
        conv_id = self._user_sessions.get(user_id)
        if conv_id:
            return self._conversations.get(conv_id)
        return None
    
    def end_conversation(self, user_id: str):
        """End a user's conversation"""
        conv_id = self._user_sessions.get(user_id)
        if conv_id and conv_id in self._conversations:
            conv = self._conversations[conv_id]
            conv.state = ConversationState.COMPLETED
            conv.expires_at = datetime.utcnow()  # Expire immediately
            del self._user_sessions[user_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation manager statistics"""
        return {
            "active_conversations": len(self._conversations),
            "user_sessions": len(self._user_sessions),
            "registered_intents": len(self._handlers),
            "uptime": "active"
        }


# Global instance
conversation_manager = ConversationManager()

# Export
__all__ = [
    'Intent',
    'ConversationState',
    'Entity',
    'ConversationContext',
    'ConversationManager',
    'conversation_manager'
]
