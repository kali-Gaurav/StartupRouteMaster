"""
Interactive Response Types
==========================

Rich response types for interactive chatbot functionality.
Supports buttons, carousels, forms, actions, and more.

Author: RouteMaster Team
Version: 1.0.0
"""

from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid


class ResponseType(str, Enum):
    """Types of interactive responses"""
    TEXT = "text"
    BUTTONS = "buttons"
    CAROUSEL = "carousel"
    FORM = "form"
    LIST = "list"
    CARD = "card"
    ACTION = "action"
    REDIRECT = "redirect"
    PROGRESS = "progress"
    CONFIRMATION = "confirmation"
    INPUT_REQUIRED = "input_required"
    DROPDOWN = "dropdown"
    TIMELINE = "timeline"
    MAP = "map"
    BOOKING_WIDGET = "booking_widget"
    PAYMENT = "payment"
    FEEDBACK = "feedback"


class ActionType(str, Enum):
    """Types of actions that can be triggered"""
    BOOK_TICKET = "book_ticket"
    CHECK_PNR = "check_pnr"
    TRACK_TRAIN = "track_train"
    CANCEL_BOOKING = "cancel_booking"
    RESCHEDULE = "reschedule"
    REDEEM_VOUCHER = "redeem_voucher"
    SHARE_ITINERARY = "share_itinerary"
    DOWNLOAD_TICKET = "download_ticket"
    ADD_TO_CALENDAR = "add_to_calendar"
    REQUEST_REFUND = "request_refund"
    RATE_JOURNEY = "rate_journey"
    REPORT_ISSUE = "report_issue"
    CONTACT_SUPPORT = "contact_support"
    GET_HELP = "get_help"
    SEARCH_TRAINS = "search_trains"
    VIEW_AMENITIES = "view_amenities"
    BOOK_WAITING = "book_waiting"
    REQUEST_CROWD_INFO = "request_crowd_info"
    INITIATE_REDISTRIBUTION = "initiate_redistribution"
    OPEN_DASHBOARD = "open_dashboard"
    VIEW_BOOKINGS = "view_bookings"
    EMERGENCY_SOS = "emergency_sos"


@dataclass
class Button:
    """Interactive button configuration"""
    text: str
    action: str
    value: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    style: str = "default"  # default, primary, danger, success
    requires_input: bool = False
    input_placeholder: Optional[str] = None
    
    def __post_init__(self):
        if not self.action:
            self.action = self.text.lower().replace(" ", "_")


@dataclass
class FormField:
    """Form field configuration"""
    field_id: str
    field_type: str  # text, number, date, time, dropdown, checkbox
    label: str
    required: bool = False
    placeholder: Optional[str] = None
    default_value: Optional[Any] = None
    options: Optional[List[Dict[str, str]]] = None  # For dropdowns
    validation: Optional[Dict[str, Any]] = None
    depends_on: Optional[str] = None  # Field ID this depends on
    action: Optional[str] = None  # Action to trigger on change
    
    def __post_init__(self):
        if not self.field_id:
            self.field_id = str(uuid.uuid4())[:8]


@dataclass
class CarouselItem:
    """Carousel item for displaying multiple options"""
    item_id: str
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    buttons: List[Button] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.item_id:
            self.item_id = str(uuid.uuid4())[:8]


@dataclass
class InteractiveResponse:
    """Complete interactive response"""
    response_id: str
    response_type: ResponseType
    content: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    
    # Interactive elements
    buttons: List[Button] = field(default_factory=list)
    carousel_items: List[CarouselItem] = field(default_factory=list)
    form_fields: List[FormField] = field(default_factory=list)
    
    # Actions
    primary_action: Optional[ActionType] = None
    secondary_actions: List[ActionType] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.response_id:
            self.response_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "response_id": self.response_id,
            "response_type": self.response_type.value,
            "content": self.content,
            "title": self.title,
            "subtitle": self.subtitle,
            "buttons": [
                {
                    "text": b.text,
                    "action": b.action,
                    "value": b.value,
                    "description": b.description,
                    "icon": b.icon,
                    "style": b.style
                }
                for b in self.buttons
            ],
            "carousel_items": [
                {
                    "item_id": ci.item_id,
                    "title": ci.title,
                    "subtitle": ci.subtitle,
                    "description": ci.description,
                    "image_url": ci.image_url,
                    "buttons": [{"text": b.text, "action": b.action} for b in ci.buttons],
                    "metadata": ci.metadata
                }
                for ci in self.carousel_items
            ],
            "form_fields": [
                {
                    "field_id": ff.field_id,
                    "field_type": ff.field_type,
                    "label": ff.label,
                    "required": ff.required,
                    "placeholder": ff.placeholder,
                    "default_value": ff.default_value,
                    "options": ff.options
                }
                for ff in self.form_fields
            ],
            "primary_action": self.primary_action.value if self.primary_action else None,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# RESPONSE BUILDERS
# ============================================================================

class InteractiveResponseBuilder:
    """Builder for creating interactive responses"""
    
    def __init__(self):
        self._response: Optional[InteractiveResponse] = None
    
    def text(self, content: str, title: Optional[str] = None) -> "InteractiveResponseBuilder":
        """Create a text response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.TEXT,
            content=content,
            title=title
        )
        return self
    
    def buttons(
        self,
        content: str,
        buttons: List[Button],
        title: Optional[str] = None
    ) -> "InteractiveResponseBuilder":
        """Create a button-based response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.BUTTONS,
            content=content,
            buttons=buttons,
            title=title
        )
        return self
    
    def carousel(
        self,
        items: List[CarouselItem],
        title: Optional[str] = None,
        content: str = ""
    ) -> "InteractiveResponseBuilder":
        """Create a carousel response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.CAROUSEL,
            content=content,
            carousel_items=items,
            title=title
        )
        return self
    
    def form(
        self,
        content: str,
        fields: List[FormField],
        title: Optional[str] = None,
        action: Optional[ActionType] = None
    ) -> "InteractiveResponseBuilder":
        """Create a form response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.FORM,
            content=content,
            form_fields=fields,
            title=title,
            primary_action=action
        )
        return self
    
    def card(
        self,
        title: str,
        content: str,
        buttons: Optional[List[Button]] = None,
        image_url: Optional[str] = None,
        subtitle: Optional[str] = None
    ) -> "InteractiveResponseBuilder":
        """Create a card response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.CARD,
            content=content,
            title=title,
            subtitle=subtitle,
            buttons=buttons or [],
            metadata={"image_url": image_url}
        )
        return self
    
    def confirmation(
        self,
        message: str,
        confirm_action: str,
        cancel_action: str,
        title: Optional[str] = None
    ) -> "InteractiveResponseBuilder":
        """Create a confirmation dialog"""
        buttons = [
            Button(text="✓ Confirm", action=confirm_action, style="success"),
            Button(text="✗ Cancel", action=cancel_action, style="danger")
        ]
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.CONFIRMATION,
            content=message,
            buttons=buttons,
            title=title
        )
        return self
    
    def progress(
        self,
        message: str,
        operation: str,
        status: str,
        progress_percent: int = 0,
        details: Optional[Dict[str, Any]] = None
    ) -> "InteractiveResponseBuilder":
        """Create a progress update response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.PROGRESS,
            content=message,
            title=operation,
            metadata={
                "status": status,
                "progress_percent": progress_percent,
                "details": details or {}
            }
        )
        return self
    
    def booking_widget(
        self,
        train_info: Dict[str, Any],
        available_classes: List[Dict[str, Any]],
        action: ActionType = ActionType.BOOK_TICKET
    ) -> "InteractiveResponseBuilder":
        """Create a booking widget response"""
        buttons = [
            Button(
                text=f"Book {cls['class_code']} - ₹{cls['fare']}",
                action=f"book_{cls['class_code'].lower()}",
                value=cls['class_code'],
                style="primary"
            )
            for cls in available_classes
        ]
        
        content = f"""
🚂 <b>{train_info.get('train_name', 'Train')}</b> ({train_info.get('train_number', '')})
📍 {train_info.get('from', '')} → {train_info.get('to', '')}
⏰ {train_info.get('departure_time', '')} - {train_info.get('arrival_time', '')}
⏱️ Duration: {train_info.get('duration', '')}
        """
        
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.BOOKING_WIDGET,
            content=content,
            buttons=buttons,
            title="Select Class to Book",
            primary_action=action,
            metadata={"train_info": train_info, "classes": available_classes}
        )
        return self
    
    def payment(
        self,
        amount: float,
        currency: str = "INR",
        description: str = "",
        methods: Optional[List[str]] = None,
        action: ActionType = ActionType.BOOK_TICKET
    ) -> "InteractiveResponseBuilder":
        """Create a payment request response"""
        buttons = [
            Button(text="💳 Pay with Card", action="pay_card", style="primary"),
            Button(text="📱 UPI", action="pay_upi", style="primary"),
            Button(text="🏦 Net Banking", action="pay_netbanking", style="default")
        ]
        
        content = f"""
💰 <b>Payment Required</b>

Amount: <b>{currency} {amount:.2f}</b>
{description}
        """
        
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.PAYMENT,
            content=content,
            buttons=buttons,
            title="Complete Payment",
            primary_action=action,
            metadata={"amount": amount, "currency": currency, "methods": methods}
        )
        return self
    
    def redirect(
        self,
        url: str,
        message: str,
        button_text: str = "Open Link",
        new_tab: bool = True
    ) -> "InteractiveResponseBuilder":
        """Create a redirect response"""
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.REDIRECT,
            content=message,
            buttons=[Button(text=button_text, action="open_link", value=url)],
            metadata={"url": url, "new_tab": new_tab}
        )
        return self
    
    def sos(
        self,
        location: Optional[str] = None,
        train_info: Optional[Dict[str, Any]] = None
    ) -> "InteractiveResponseBuilder":
        """Create an SOS emergency response"""
        buttons = [
            Button(text="🚨 Call Emergency", action="call_emergency", style="danger"),
            Button(text="📞 Contact Railway", action="contact_railway", style="danger"),
            Button(text="🏥 Medical Help", action="medical_help", style="danger"),
            Button(text="👮 Police", action="police_help", style="danger"),
            Button(text="❌ Cancel", action="cancel_sos", style="default")
        ]
        
        content = "🚨 <b>EMERGENCY SERVICES</b>\n\n"
        if location:
            content += f"📍 Location: {location}\n"
        if train_info:
            content += f"🚂 Train: {train_info.get('train_number', '')} - {train_info.get('train_name', '')}\n"
        
        content += "\nSelect an emergency service:"
        
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.ACTION,
            content=content,
            buttons=buttons,
            title="Emergency Assistance",
            primary_action=ActionType.EMERGENCY_SOS,
            metadata={"location": location, "train_info": train_info}
        )
        return self
    
    def feedback(
        self,
        journey_id: str,
        question: str = "How was your journey?"
    ) -> "InteractiveResponseBuilder":
        """Create a feedback request response"""
        buttons = [
            Button(text="⭐⭐⭐⭐⭐ Excellent", action="rate_5", value="5", style="success"),
            Button(text="⭐⭐⭐⭐ Good", action="rate_4", value="4", style="success"),
            Button(text="⭐⭐⭐ Average", action="rate_3", value="3", style="default"),
            Button(text="⭐⭐ Poor", action="rate_2", value="2", style="danger"),
            Button(text="⭐ Terrible", action="rate_1", value="1", style="danger")
        ]
        
        self._response = InteractiveResponse(
            response_id=str(uuid.uuid4()),
            response_type=ResponseType.FEEDBACK,
            content=question,
            buttons=buttons,
            title="Rate Your Journey",
            primary_action=ActionType.RATE_JOURNEY,
            metadata={"journey_id": journey_id}
        )
        return self
    
    def build(self) -> InteractiveResponse:
        """Build the response"""
        if not self._response:
            raise ValueError("No response type selected")
        return self._response


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_search_results(
    trains: List[Dict[str, Any]],
    search_params: Dict[str, Any]
) -> InteractiveResponse:
    """Create interactive search results with booking options"""
    items = []
    for train in trains[:5]:  # Limit to 5 results
        classes = train.get('classes', [])
        class_buttons = [
            Button(
                text=f"{cls['class_code']} - ₹{cls['fare']}",
                action=f"book_{cls['class_code'].lower()}",
                value=cls['class_code'],
                style="primary" if cls['available'] else "default"
            )
            for cls in classes[:3]
        ]
        
        item = CarouselItem(
            item_id=train.get('train_number', str(uuid.uuid4())[:8]),
            title=f"🚂 {train.get('train_name', 'Train')}",
            subtitle=f"{train.get('from', '')} → {train.get('to', '')}",
            description=f"⏰ {train.get('departure_time', '')} - {train.get('arrival_time', '')} | ⏱️ {train.get('duration', '')}",
            buttons=class_buttons,
            metadata=train
        )
        items.append(item)
    
    return (InteractiveResponseBuilder()
        .carousel(
            items=items,
            title=f"Search Results: {search_params.get('from', '')} → {search_params.get('to', '')}",
            content=f"Found {len(trains)} trains for {search_params.get('date', '')}"
        )
        .build())


def create_booking_confirmation(
    booking_details: Dict[str, Any]
) -> InteractiveResponse:
    """Create booking confirmation with action buttons"""
    buttons = [
        Button(text="📥 Download Ticket", action="download_ticket", style="primary"),
        Button(text="📅 Add to Calendar", action="add_to_calendar", style="default"),
        Button(text="📤 Share Itinerary", action="share_itinerary", style="default"),
        Button(text="🔍 Track Live Status", action="track_train", style="default")
    ]
    
    content = f"""
✅ <b>Booking Confirmed!</b>

🎫 PNR: <code>{booking_details.get('pnr', 'N/A')}</code>
🚂 Train: {booking_details.get('train_name', 'N/A')}
📍 From: {booking_details.get('from', 'N/A')}
📍 To: {booking_details.get('to', 'N/A')}
📅 Date: {booking_details.get('date', 'N/A')}
⏰ Departure: {booking_details.get('departure_time', 'N/A')}
🪑 Class: {booking_details.get('class', 'N/A')}
💰 Paid: ₹{booking_details.get('fare', 'N/A')}
    """
    
    return (InteractiveResponseBuilder()
        .card(
            title="Booking Confirmed!",
            content=content,
            buttons=buttons,
            image_url=booking_details.get('train_image_url')
        )
        .build())


def create_pnr_status(
    pnr_details: Dict[str, Any]
) -> InteractiveResponse:
    """Create PNR status response with actions"""
    status = pnr_details.get('status', 'UNKNOWN')
    status_emoji = {
        'CONFIRMED': '✅',
        'RAC': '🟡',
        'WAITING': '🟠',
        'CANCELLED': '❌',
        'UNKNOWN': '❓'
    }.get(status, '❓')
    
    buttons = [
        Button(text="🔍 Track Live", action="track_train", style="primary"),
        Button(text="📅 Check Availability", action="check_availability", style="default"),
        Button(text="🔄 Reschedule", action="reschedule", style="default"),
        Button(text="❌ Cancel", action="cancel_booking", style="danger")
    ]
    
    content = f"""
{status_emoji} <b>PNR Status: {status}</b>

🎫 PNR: <code>{pnr_details.get('pnr', 'N/A')}</code>
🚂 Train: {pnr_details.get('train_name', 'N/A')}
📍 {pnr_details.get('from', 'N/A')} → {pnr_details.get('to', 'N/A')}
📅 {pnr_details.get('date', 'N/A')}
🪑 {pnr_details.get('class', 'N/A')} - Berth: {pnr_details.get('berth', 'N/A')}
    """
    
    if pnr_details.get('coach_position'):
        content += f"\n🚃 Coach Position: {pnr_details.get('coach_position')}"
    
    return (InteractiveResponseBuilder()
        .card(
            title="PNR Status",
            content=content,
            buttons=buttons
        )
        .build())


def create_train_tracking(
    train_info: Dict[str, Any]
) -> InteractiveResponse:
    """Create train tracking response with live updates"""
    buttons = [
        Button(text="🔄 Refresh", action="refresh_tracking", style="primary"),
        Button(text="📍 View on Map", action="view_map", style="default"),
        Button(text="🚉 Station Info", action="station_info", style="default"),
        Button(text="👥 Crowd Info", action="crowd_info", style="default")
    ]
    
    content = f"""
🚂 <b>Live Train Tracking</b>

{train_info.get('train_number', '')} - {train_info.get('train_name', 'N/A')}

📍 <b>Current Location:</b> {train_info.get('current_station', 'N/A')}
⏰ <b>Last Update:</b> {train_info.get('last_update', 'N/A')}

📊 <b>Delay:</b> {train_info.get('delay_minutes', 0)} minutes
📈 <b>Speed:</b> {train_info.get('current_speed', 'N/A')}

🛤️ <b>Next Stop:</b> {train_info.get('next_station', 'N/A')} ({train_info.get('next_arrival', 'N/A')})
    """
    
    return (InteractiveResponseBuilder()
        .card(
            title="Live Train Status",
            content=content,
            buttons=buttons,
            image_url=train_info.get('map_url')
        )
        .build())


# Export
__all__ = [
    'ResponseType',
    'ActionType',
    'Button',
    'FormField',
    'CarouselItem',
    'InteractiveResponse',
    'InteractiveResponseBuilder',
    'create_search_results',
    'create_booking_confirmation',
    'create_pnr_status',
    'create_train_tracking'
]