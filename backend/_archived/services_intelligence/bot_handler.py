"""
Interactive Bot Handler
=======================

Handles interactive bot conversations with rich responses.
Integrates with Telegram and web platforms.

Author: RouteMaster Team
Version: 1.0.0
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid

from .response_types import (
    InteractiveResponse, ResponseType, ActionType, Button, CarouselItem,
    FormField, InteractiveResponseBuilder, create_search_results,
    create_booking_confirmation, create_pnr_status, create_train_tracking
)
from .conversation import (
    ConversationManager, ConversationContext, Intent, ConversationState
)
from services.telegram.bot import TelegramDispatcher

logger = logging.getLogger("bot.handler")


class Platform(str, Enum):
    """Supported platforms"""
    TELEGRAM = "telegram"
    WEB = "web"
    WHATSAPP = "whatsapp"


@dataclass
class BotAction:
    """Bot action to execute"""
    action_id: str
    action_type: ActionType
    user_id: str
    conversation_id: str
    data: Dict[str, Any]
    timestamp: datetime
    requires_confirmation: bool = False
    confirmed: bool = False
    
    def __post_init__(self):
        if not self.action_id:
            self.action_id = str(uuid.uuid4())


class InteractiveBotHandler:
    """
    Main bot handler for interactive conversations.
    Processes user messages and generates rich responses.
    """
    
    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.telegram = TelegramDispatcher()
        self._action_handlers: Dict[ActionType, Callable] = {}
        self._platform_adapters: Dict[Platform, Callable] = {}
        self._action_queue: asyncio.Queue = asyncio.Queue()
        self._processing_actions = False
        
        # Register default action handlers
        self._register_default_handlers()
        
        logger.info("InteractiveBotHandler initialized")
    
    def _register_default_handlers(self):
        """Register default action handlers"""
        self.register_action_handler(ActionType.BOOK_TICKET, self._handle_book_ticket)
        self.register_action_handler(ActionType.CHECK_PNR, self._handle_check_pnr)
        self.register_action_handler(ActionType.TRACK_TRAIN, self._handle_track_train)
        self.register_action_handler(ActionType.CANCEL_BOOKING, self._handle_cancel_booking)
        self.register_action_handler(ActionType.RESCHEDULE, self._handle_reschedule)
        self.register_action_handler(ActionType.DOWNLOAD_TICKET, self._handle_download_ticket)
        self.register_action_handler(ActionType.ADD_TO_CALENDAR, self._handle_add_to_calendar)
        self.register_action_handler(ActionType.SHARE_ITINERARY, self._handle_share_itinerary)
        self.register_action_handler(ActionType.EMERGENCY_SOS, self._handle_emergency_sos)
        self.register_action_handler(ActionType.VIEW_BOOKINGS, self._handle_view_bookings)
        self.register_action_handler(ActionType.OPEN_DASHBOARD, self._handle_open_dashboard)
        self.register_action_handler(ActionType.REQUEST_REFUND, self._handle_request_refund)
        self.register_action_handler(ActionType.RATE_JOURNEY, self._handle_rate_journey)
        self.register_action_handler(ActionType.REPORT_ISSUE, self._handle_report_issue)
        self.register_action_handler(ActionType.VIEW_AMENITIES, self._handle_view_amenities)
        self.register_action_handler(ActionType.BOOK_WAITING, self._handle_book_waiting)
        self.register_action_handler(ActionType.REQUEST_CROWD_INFO, self._handle_crowd_info)
    
    def register_action_handler(self, action_type: ActionType, handler: Callable):
        """Register a handler for an action type"""
        self._action_handlers[action_type] = handler
        logger.debug(f"Registered handler for action: {action_type.value}")
    
    def register_platform_adapter(self, platform: Platform, adapter: Callable):
        """Register a platform-specific adapter"""
        self._platform_adapters[platform] = adapter
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        platform: Platform = Platform.TELEGRAM,
        chat_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> InteractiveResponse:
        """
        Process a user message and return an interactive response.
        
        Args:
            user_id: User identifier
            message: User message
            platform: Platform (telegram, web, etc.)
            chat_id: Platform-specific chat ID
            metadata: Additional metadata
            
        Returns:
            InteractiveResponse
        """
        try:
            # Get conversation context
            conv = self.conversation_manager.get_or_create_conversation(
                user_id=user_id,
                platform=platform.value
            )
            
            # Update metadata
            if metadata:
                conv.metadata.update(metadata)
            
            # Process message through conversation manager
            response = self.conversation_manager.process_message(
                user_id=user_id,
                message=message,
                platform=platform.value,
                context=conv
            )
            
            # Send response to platform
            await self._send_response(user_id, chat_id, response, platform)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return self._get_error_response(str(e))
    
    async def process_callback(
        self,
        user_id: str,
        action: str,
        value: Optional[str] = None,
        conversation_id: Optional[str] = None,
        platform: Platform = Platform.TELEGRAM,
        chat_id: Optional[str] = None
    ) -> InteractiveResponse:
        """
        Process a callback query (button click, etc.)
        
        Args:
            user_id: User identifier
            action: Action identifier
            value: Action value
            conversation_id: Conversation ID
            platform: Platform
            chat_id: Platform chat ID
            
        Returns:
            InteractiveResponse
        """
        try:
            # Get conversation
            conv = None
            if conversation_id:
                conv = self.conversation_manager.get_conversation(conversation_id)
            if not conv:
                conv = self.conversation_manager.get_or_create_conversation(user_id, platform.value)
            
            # Create action
            action_type = self._parse_action_type(action)
            bot_action = BotAction(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                user_id=user_id,
                conversation_id=conv.conversation_id,
                data={"action": action, "value": value},
                timestamp=datetime.utcnow()
            )
            
            # Check if action requires confirmation
            if self._requires_confirmation(action_type):
                return self._create_confirmation_response(bot_action)
            
            # Execute action
            response = await self._execute_action(bot_action, conv)
            
            # Send response
            await self._send_response(user_id, chat_id, response, platform)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            return self._get_error_response(str(e))
    
    async def _send_response(
        self,
        user_id: str,
        chat_id: Optional[str],
        response: InteractiveResponse,
        platform: Platform
    ):
        """Send response to the appropriate platform"""
        adapter = self._platform_adapters.get(platform)
        if adapter:
            await adapter(user_id, chat_id, response)
        else:
            # Default to Telegram
            if chat_id:
                await self._send_telegram_response(chat_id, response)
    
    async def _send_telegram_response(self, chat_id: str, response: InteractiveResponse):
        """Send response to Telegram"""
        try:
            # Convert to Telegram format
            telegram_format = self._to_telegram_format(response)
            
            if response.response_type == ResponseType.BUTTONS:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=response.content,
                    reply_markup=telegram_format.get("reply_markup")
                )
            elif response.response_type == ResponseType.CARD:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=response.content,
                    reply_markup=telegram_format.get("reply_markup")
                )
            elif response.response_type == ResponseType.CAROUSEL:
                # Send as multiple cards for Telegram
                for item in response.carousel_items:
                    item_text = f"🚂 <b>{item.title}</b>\n\n{item.description or ''}"
                    item_buttons = [
                        {"text": b.text, "callback_data": b.action}
                        for b in item.buttons
                    ]
                    await self.telegram.send_message(
                        chat_id=chat_id,
                        text=item_text,
                        reply_markup={"inline_keyboard": [item_buttons]} if item_buttons else None
                    )
            elif response.response_type == ResponseType.ACTION and response.primary_action == ActionType.EMERGENCY_SOS:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=response.content,
                    reply_markup=telegram_format.get("reply_markup")
                )
            else:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=response.content
                )
                
        except Exception as e:
            logger.error(f"Error sending Telegram response: {e}")
    
    def _to_telegram_format(self, response: InteractiveResponse) -> Dict[str, Any]:
        """Convert response to Telegram format"""
        result = {}
        
        if response.buttons:
            keyboard = []
            for button in response.buttons:
                keyboard.append([{
                    "text": button.text,
                    "callback_data": button.action
                }])
            result["reply_markup"] = {"inline_keyboard": keyboard}
        
        return result
    
    def _parse_action_type(self, action: str) -> ActionType:
        """Parse action string to ActionType"""
        action_map = {
            "book_ticket": ActionType.BOOK_TICKET,
            "check_pnr": ActionType.CHECK_PNR,
            "track_train": ActionType.TRACK_TRAIN,
            "cancel_booking": ActionType.CANCEL_BOOKING,
            "reschedule": ActionType.RESCHEDULE,
            "download_ticket": ActionType.DOWNLOAD_TICKET,
            "add_to_calendar": ActionType.ADD_TO_CALENDAR,
            "share_itinerary": ActionType.SHARE_ITINERARY,
            "sos": ActionType.EMERGENCY_SOS,
            "my_bookings": ActionType.VIEW_BOOKINGS,
            "dashboard": ActionType.OPEN_DASHBOARD,
            "help": ActionType.GET_HELP,
            "search_trains": ActionType.SEARCH_TRAINS,
            "rate_journey": ActionType.RATE_JOURNEY,
            "report_issue": ActionType.REPORT_ISSUE,
            "view_amenities": ActionType.VIEW_AMENITIES,
            "book_waiting": ActionType.BOOK_WAITING,
            "crowd_info": ActionType.REQUEST_CROWD_INFO
        }
        
        return action_map.get(action.lower(), ActionType.BOOK_TICKET)
    
    def _requires_confirmation(self, action_type: ActionType) -> bool:
        """Check if action requires confirmation"""
        confirm_actions = {
            ActionType.CANCEL_BOOKING,
            ActionType.RESCHEDULE,
            ActionType.REQUEST_REFUND
        }
        return action_type in confirm_actions
    
    def _create_confirmation_response(self, action: BotAction) -> InteractiveResponse:
        """Create confirmation dialog for action"""
        action_names = {
            ActionType.CANCEL_BOOKING: "Cancel Booking",
            ActionType.RESCHEDULE: "Reschedule Booking",
            ActionType.REQUEST_REFUND: "Request Refund"
        }
        
        return (InteractiveResponseBuilder()
            .confirmation(
                message=f"Are you sure you want to {action_names.get(action.action_type, 'perform this action')}?",
                confirm_action=f"confirm_{action.action_type.value}",
                cancel_action="cancel_action",
                title="Confirmation Required"
            )
            .build())
    
    async def _execute_action(
        self,
        action: BotAction,
        conv: ConversationContext
    ) -> InteractiveResponse:
        """Execute an action and return response"""
        handler = self._action_handlers.get(action.action_type)
        
        if handler:
            return await handler(action, conv)
        
        # Default response
        return (InteractiveResponseBuilder()
            .text(f"Action {action.action_type.value} completed successfully.")
            .build())
    
    # =========================================================================
    # ACTION HANDLERS
    # =========================================================================
    
    async def _handle_book_ticket(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle book ticket action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Please provide booking details:",
                fields=[
                    FormField(field_id="from", field_type="text", label="From", required=True),
                    FormField(field_id="to", field_type="text", label="To", required=True),
                    FormField(field_id="date", field_type="date", label="Date", required=True),
                    FormField(
                        field_id="class",
                        field_type="dropdown",
                        label="Class",
                        required=True,
                        options=[
                            {"value": "SL", "label": "Sleeper"},
                            {"value": "3A", "label": "AC 3-Tier"},
                            {"value": "2A", "label": "AC 2-Tier"},
                            {"value": "1A", "label": "AC First Class"}
                        ]
                    )
                ],
                action=ActionType.BOOK_TICKET
            )
            .build())
    
    async def _handle_check_pnr(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle check PNR action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Enter your 10-digit PNR number:",
                fields=[
                    FormField(
                        field_id="pnr",
                        field_type="text",
                        label="PNR Number",
                        required=True,
                        validation={"pattern": r"^\d{10}$", "message": "Invalid PNR format"}
                    )
                ],
                action=ActionType.CHECK_PNR
            )
            .build())
    
    async def _handle_track_train(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle track train action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Enter train number to track:",
                fields=[
                    FormField(field_id="train_number", field_type="text", label="Train Number", required=True)
                ],
                action=ActionType.TRACK_TRAIN
            )
            .build())
    
    async def _handle_cancel_booking(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle cancel booking action"""
        return (InteractiveResponseBuilder()
            .confirmation(
                message="Are you sure you want to cancel this booking? Cancellation charges may apply.",
                confirm_action="confirm_cancel",
                cancel_action="cancel_cancel",
                title="Cancel Booking"
            )
            .build())
    
    async def _handle_reschedule(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle reschedule action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Select new travel date:",
                fields=[
                    FormField(field_id="new_date", field_type="date", label="New Date", required=True)
                ],
                action=ActionType.RESCHEDULE
            )
            .build())
    
    async def _handle_download_ticket(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle download ticket action"""
        return (InteractiveResponseBuilder()
            .redirect(
                url="https://routemaster.app/ticket/download",
                message="📥 Your ticket is ready for download!",
                button_text="Download Ticket"
            )
            .build())
    
    async def _handle_add_to_calendar(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle add to calendar action"""
        return (InteractiveResponseBuilder()
            .redirect(
                url="https://routemaster.app/calendar/add",
                message="📅 Add this journey to your calendar",
                button_text="Add to Calendar"
            )
            .build())
    
    async def _handle_share_itinerary(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle share itinerary action"""
        return (InteractiveResponseBuilder()
            .buttons(
                content="Share your itinerary via:",
                buttons=[
                    Button(text="📱 WhatsApp", action="share_whatsapp"),
                    Button(text="📧 Email", action="share_email"),
                    Button(text="📋 Copy Link", action="copy_link")
                ]
            )
            .build())
    
    async def _handle_emergency_sos(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle emergency SOS action"""
        return (InteractiveResponseBuilder()
            .sos(
                location=conv.entities.get('location'),
                train_info=conv.entities.get('train_info')
            )
            .build())
    
    async def _handle_view_bookings(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle view bookings action"""
        return (InteractiveResponseBuilder()
            .redirect(
                url="https://routemaster.app/bookings",
                message="📋 View all your bookings on the website",
                button_text="Open Bookings"
            )
            .build())
    
    async def _handle_open_dashboard(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle open dashboard action"""
        return (InteractiveResponseBuilder()
            .redirect(
                url="https://routemaster.app/dashboard",
                message="📊 Open your RouteMaster dashboard",
                button_text="Open Dashboard"
            )
            .build())
    
    async def _handle_request_refund(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle request refund action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Please provide refund details:",
                fields=[
                    FormField(
                        field_id="reason",
                        field_type="dropdown",
                        label="Reason",
                        required=True,
                        options=[
                            {"value": "cancellation", "label": "Train Cancelled"},
                            {"value": "delay", "label": "Train Delayed > 3hrs"},
                            {"value": "medical", "label": "Medical Emergency"},
                            {"value": "other", "label": "Other"}
                        ]
                    ),
                    FormField(
                        field_id="details",
                        field_type="text",
                        label="Additional Details",
                        required=False
                    )
                ],
                action=ActionType.REQUEST_REFUND
            )
            .build())
    
    async def _handle_rate_journey(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle rate journey action"""
        rating = action.data.get('value', '0')
        
        return (InteractiveResponseBuilder()
            .feedback(
                journey_id=conv.entities.get('journey_id', ''),
                question=f"You rated this journey {rating} stars. Would you like to add any comments?"
            )
            .build())
    
    async def _handle_report_issue(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle report issue action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Report an issue with your journey:",
                fields=[
                    FormField(
                        field_id="issue_type",
                        field_type="dropdown",
                        label="Issue Type",
                        required=True,
                        options=[
                            {"value": "cleanliness", "label": "Cleanliness"},
                            {"value": "food", "label": "Food Quality"},
                            {"value": "behavior", "label": "Staff Behavior"},
                            {"value": "delay", "label": "Undue Delay"},
                            {"value": "crowd", "label": "Overcrowding"},
                            {"value": "other", "label": "Other"}
                        ]
                    ),
                    FormField(
                        field_id="description",
                        field_type="text",
                        label="Description",
                        required=True
                    ),
                    FormField(
                        field_id="photos",
                        field_type="text",
                        label="Photo URLs (optional)",
                        required=False
                    )
                ],
                action=ActionType.REPORT_ISSUE
            )
            .build())
    
    async def _handle_view_amenities(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle view amenities action"""
        station = conv.entities.get('station_code', 'NDLS')
        
        return (InteractiveResponseBuilder()
            .redirect(
                url=f"https://routemaster.app/stations/{station}/amenities",
                message=f"🛋️ View amenities at {station} station",
                button_text="View Amenities"
            )
            .build())
    
    async def _handle_book_waiting(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle book waiting lounge action"""
        return (InteractiveResponseBuilder()
            .form(
                content="Book a waiting lounge:",
                fields=[
                    FormField(
                        field_id="station",
                        field_type="text",
                        label="Station",
                        required=True
                    ),
                    FormField(
                        field_id="package",
                        field_type="dropdown",
                        label="Package",
                        required=True,
                        options=[
                            {"value": "basic", "label": "Basic (₹50/2hr)"},
                            {"value": "standard", "label": "Standard (₹200/3hr)"},
                            {"value": "premium", "label": "Premium (₹500/4hr)"},
                            {"value": "family", "label": "Family (₹400/4hr)"}
                        ]
                    ),
                    FormField(
                        field_id="date",
                        field_type="date",
                        label="Date",
                        required=True
                    ),
                    FormField(
                        field_id="time",
                        field_type="time",
                        label="Time",
                        required=True
                    )
                ],
                action=ActionType.BOOK_WAITING
            )
            .build())
    
    async def _handle_crowd_info(self, action: BotAction, conv: ConversationContext) -> InteractiveResponse:
        """Handle crowd info action"""
        return (InteractiveResponseBuilder()
            .redirect(
                url="https://routemaster.app/crowd-map",
                message="👥 View real-time crowd information",
                button_text="View Crowd Map"
            )
            .build())
    
    def _get_error_response(self, error: str) -> InteractiveResponse:
        """Get error response"""
        return (InteractiveResponseBuilder()
            .card(
                title="⚠️ Something went wrong",
                content=f"We encountered an error: {error}\n\nPlease try again or contact support.",
                buttons=[
                    Button(text="Try Again", action="retry", icon="refresh"),
                    Button(text="Get Help", action="help", icon="help")
                ]
            )
            .build())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        return {
            "conversation_manager": self.conversation_manager.get_stats(),
            "registered_actions": len(self._action_handlers),
            "registered_platforms": len(self._platform_adapters)
        }


# Global instance
interactive_bot_handler = InteractiveBotHandler()

# Export
__all__ = [
    'Platform',
    'BotAction',
    'InteractiveBotHandler',
    'interactive_bot_handler'
]
