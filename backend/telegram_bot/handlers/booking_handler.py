"""
Booking Handler
===============
Handles ticket booking and management.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType, HandlerResult, HandlerResultStatus
)
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder
from ..user_session_manager import user_session_manager
from ..config import feature_config

logger = logging.getLogger(__name__)


class BookingHandler:
    """Handles ticket booking and management."""
    
    BOOKING_FLOW = [
        "select_train",
        "select_class",
        "select_quota",
        "enter_passengers",
        "review_booking",
        "payment",
        "confirmation"
    ]
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle booking requests.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        text = message.text or ""
        entities = intent_result.entities
        
        try:
            # Get current booking step
            current_step = context.data.get("booking_step", "start")
            
            # Route to appropriate step handler
            step_handlers = {
                "start": self._handle_booking_start,
                "select_train": self._handle_train_selection,
                "select_class": self._handle_class_selection,
                "select_quota": self._handle_quota_selection,
                "enter_passengers": self._handle_passenger_entry,
                "review_booking": self._handle_review,
                "payment": self._handle_payment,
            }
            
            handler = step_handlers.get(current_step, self._handle_booking_start)
            return await handler(chat_id, text, context, entities)
            
        except Exception as e:
            logger.error(f"Error in booking handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Booking Error</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _handle_booking_start(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Start booking flow."""
        # Check if train is already selected
        if context.data.get("selected_train"):
            return await self._handle_train_selection(
                chat_id, text, context, entities
            )
        
        text = """🎫 <b>Start Booking</b>

To book a ticket, I need some information:

<b>Step 1:</b> Search for trains
━━━━━━━━━━━━━━━━━━━━━━━━
Please search for trains first using:
• 🔍 Search Trains button, or
• Type: <i>"Trains from [from] to [to]"</i>

Once you find a train, tap "Book Now" to continue.
━━━━━━━━━━━━━━━━━━━━━━━━

<i>Need help? Type /help</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard_builder.search_menu()
            ),
            next_state="booking",
            data={"booking_step": "start"}
        )
    
    async def _handle_train_selection(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle train selection."""
        train_data = context.data.get("selected_train", {})
        
        text = f"""🚂 <b>Train Selected</b>

<b>{train_data.get('train_no', 'N/A')} - {train_data.get('train_name', 'Express')}</b>
{train_data.get('departure', 'N/A')} → {train_data.get('arrival', 'N/A')}
Duration: {train_data.get('duration', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Step 2: Select Class</b>
━━━━━━━━━━━━━━━━━━━━━━━━

Choose your travel class:"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=keyboard_builder.class_selection()
            ),
            next_state="booking",
            data={"booking_step": "select_class"}
        )
    
    async def _handle_class_selection(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle class selection."""
        # Parse class from callback or text
        class_map = {
            "class_1A": "AC First Class (1A)",
            "class_2A": "AC 2-Tier (2A)",
            "class_3A": "AC 3-Tier (3A)",
            "class_CC": "AC Chair Car (CC)",
            "class_SL": "Sleeper (SL)",
            "class_2S": "Second Sitting (2S)"
        }
        
        selected_class = class_map.get(text, text)
        
        # Update context
        booking_data = context.data.get("booking_data", {})
        booking_data["class"] = selected_class
        
        text = f"""🎫 <b>Class Selected</b>

Class: <b>{selected_class}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Step 3: Select Quota</b>
━━━━━━━━━━━━━━━━━━━━━━━━

Choose your booking quota:"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=keyboard_builder.quota_selection()
            ),
            next_state="booking",
            data={
                "booking_step": "select_quota",
                "booking_data": booking_data
            }
        )
    
    async def _handle_quota_selection(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle quota selection."""
        quota_map = {
            "quota_general": "General",
            "quota_tatkal": "Tatkal",
            "quota_ladies": "Ladies",
            "quota_senior": "Senior Citizen",
            "quota_divyang": "Divyang",
            "quota_premium_tatkal": "Premium Tatkal"
        }
        
        selected_quota = quota_map.get(text, text)
        
        booking_data = context.data.get("booking_data", {})
        booking_data["quota"] = selected_quota
        
        text = f"""📋 <b>Quota Selected</b>

Quota: <b>{selected_quota}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Step 4: Passenger Details</b>
━━━━━━━━━━━━━━━━━━━━━━━━

Enter passenger details in format:
<i>Name, Age, Gender (M/F)</i>

Example:
<i>John Doe, 25, M</i>
<i>Jane Smith, 22, F</i>

<i>One passenger per line. Max {feature_config.booking_max_passengers} passengers.</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard_builder.back_only()
            ),
            next_state="booking",
            data={
                "booking_step": "enter_passengers",
                "booking_data": booking_data
            }
        )
    
    async def _handle_passenger_entry(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle passenger entry."""
        # Parse passengers
        passengers = []
        lines = text.strip().split('\n')
        
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                try:
                    passenger = {
                        "name": parts[0],
                        "age": int(parts[1]),
                        "gender": parts[2].upper()[0]  # M or F
                    }
                    if len(parts) > 3:
                        passenger["berth_preference"] = parts[3]
                    passengers.append(passenger)
                except (ValueError, IndexError):
                    pass
        
        if not passengers:
            return HandlerResult(
                status=HandlerResultStatus.NEEDS_INPUT,
                response=BotResponse(
                    chat_id=chat_id,
                    text="❌ <b>Invalid Format</b>\n\nPlease enter passenger details correctly.\n\nExample:\n<i>John Doe, 25, M</i>"
                ),
                next_state="booking",
                data={"booking_step": "enter_passengers"}
            )
        
        booking_data = context.data.get("booking_data", {})
        booking_data["passengers"] = passengers
        booking_data["passenger_count"] = len(passengers)
        
        # Create review summary
        summary = self._create_booking_summary(context.data.get("selected_train", {}), booking_data)
        
        text = f"""✅ <b>Passengers Added</b>

{len(passengers)} passenger(s) registered.

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Step 5: Review Booking</b>
━━━━━━━━━━━━━━━━━━━━━━━━

{summary}

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Tap "Confirm" to proceed to payment, or "Back" to make changes.</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=keyboard_builder.booking_confirmation("temp")
            ),
            next_state="booking",
            data={
                "booking_step": "review_booking",
                "booking_data": booking_data
            }
        )
    
    async def _handle_review(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle booking review and confirmation."""
        if "confirm" in text.lower():
            # Proceed to payment
            return await self._handle_payment(chat_id, text, context, entities)
        elif "cancel" in text.lower():
            # Cancel booking
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="❌ <b>Booking Cancelled</b>\n\nYour booking has been cancelled.",
                    keyboard=keyboard_builder.main_menu()
                ),
                next_state="idle",
                data={"booking_step": None, "selected_train": None, "booking_data": None}
            )
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text="Please confirm or cancel the booking."
            ),
            next_state="booking"
        )
    
    async def _handle_payment(
        self,
        chat_id: int,
        text: str,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Handle payment processing."""
        booking_data = context.data.get("booking_data", {})
        
        # Calculate fare (mock)
        fare = self._calculate_fare(booking_data)
        
        text = f"""💳 <b>Payment</b>

<b>Booking Summary:</b>
• Passengers: {booking_data.get('passenger_count', 1)}
• Class: {booking_data.get('class', 'N/A')}
• Quota: {booking_data.get('quota', 'General')}

<b>Total Fare: ₹{fare}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Select Payment Method:</b>
━━━━━━━━━━━━━━━━━━━━━━━━

• 💰 Wallet Balance
• 💳 Card/UPI
• 📱 Net Banking

<i>Payment timeout: {feature_config.booking_payment_timeout_minutes} minutes</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "💰 Pay with Wallet", "callback_data": "pay_wallet"},
                        {"text": "💳 Card/UPI", "callback_data": "pay_card"}
                    ],
                    [
                        {"text": "🔙 Back", "callback_data": "pay_back"}
                    ]
                ]
            ),
            next_state="payment",
            data={
                "booking_step": "payment",
                "fare": fare
            }
        )
    
    def _create_booking_summary(
        self, 
        train_data: Dict[str, Any], 
        booking_data: Dict[str, Any]
    ) -> str:
        """Create booking summary text."""
        summary = []
        
        # Train info
        summary.append(f"🚂 <b>{train_data.get('train_no', 'N/A')} - {train_data.get('train_name', 'Express')}</b>")
        summary.append(f"{train_data.get('departure', 'N/A')} → {train_data.get('arrival', 'N/A')}")
        summary.append("")
        
        # Class & quota
        summary.append(f"🎫 Class: {booking_data.get('class', 'N/A')}")
        summary.append(f"📋 Quota: {booking_data.get('quota', 'General')}")
        summary.append("")
        
        # Passengers
        summary.append("<b>Passengers:</b>")
        for i, p in enumerate(booking_data.get("passengers", []), 1):
            summary.append(f"{i}. {p.get('name', 'N/A')} ({p.get('age', 0)} {p.get('gender', 'N/A')})")
        
        return "\n".join(summary)
    
    def _calculate_fare(self, booking_data: Dict[str, Any]) -> float:
        """Calculate booking fare (mock implementation)."""
        base_fares = {
            "AC First Class (1A)": 3500,
            "AC 2-Tier (2A)": 2500,
            "AC 3-Tier (3A)": 1500,
            "AC Chair Car (CC)": 1000,
            "Sleeper (SL)": 500,
            "Second Sitting (2S)": 300
        }
        
        class_type = booking_data.get("class", "Sleeper (SL)")
        base_fare = base_fares.get(class_type, 500)
        
        passenger_count = booking_data.get("passenger_count", 1)
        
        return base_fare * passenger_count
    
    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle inline callback queries for booking."""
        try:
            action, value = callback_data.split("_", 1) if "_" in callback_data else (callback_data, "")
            
            if action == "book":
                # User selected a train to book
                train_info = {
                    "train_no": value,
                    "train_name": "Selected Train",
                    "departure": "18:00",
                    "arrival": "06:00",
                    "duration": "12h"
                }
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="🚂 <b>Train Selected for Booking</b>\n\nProceeding to class selection...",
                        inline_keyboards=keyboard_builder.class_selection()
                    ),
                    next_state="booking",
                    data={
                        "booking_step": "select_class",
                        "selected_train": train_info
                    }
                )
            
            elif action == "class":
                return await self._handle_class_selection(
                    chat_id, callback_data, context, {}
                )
            
            elif action == "quota":
                return await self._handle_quota_selection(
                    chat_id, callback_data, context, {}
                )
            
            elif action == "confirm":
                return await self._handle_payment(
                    chat_id, "confirm", context, {}
                )
            
            elif action == "cancel":
                return await self._handle_review(
                    chat_id, "cancel", context, {}
                )
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Processing..."
                )
            )
            
        except Exception as e:
            logger.error(f"Error in booking callback: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )


# Global instance
booking_handler = BookingHandler()