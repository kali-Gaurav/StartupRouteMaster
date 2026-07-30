"""
PNR Handler
===========
Handles PNR status queries and booking management.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType
)
from ..command_router import HandlerResult, HandlerResultStatus
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder
from ..user_session_manager import user_session_manager
from services.booking.pnr import PNRStatusService
from services.realtime_ingestion.live_status_service import LiveStatusService

logger = logging.getLogger(__name__)


class LiveStatusHandler:
    """Handles live train status queries."""
    
    def __init__(self):
        self.live_service = LiveStatusService()
        self.pnr_service = PNRStatusService()

    async def handle_pnr_live_status(self, chat_id: int, pnr: str) -> HandlerResult:
        """Fetch live status for a train associated with a PNR."""
        try:
            pnr_data = await self.pnr_service.get_status(pnr)
            if not pnr_data or not pnr_data.get("success"):
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"❌ <b>Error</b>\n\nCould not fetch train details for PNR <code>{pnr}</code>"
                    )
                )
            
            train_no = self._extract_train_no(pnr_data)
            if not train_no:
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="❌ <b>Error</b>\n\nTrain number not found in PNR data."
                    )
                )
                
            return await self.handle_train_live_status(chat_id, train_no)
            
        except Exception as e:
            logger.error(f"Error in pnr live status: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))

    async def handle_train_live_status(self, chat_id: int, train_no: str) -> HandlerResult:
        """Fetch live status for a specific train number."""
        try:
            status_data = await self.live_service.get_live_status(train_no)
            
            if not status_data:
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"❌ <b>Live Status Unavailable</b>\n\nCould not fetch status for Train <b>{train_no}</b> at this moment."
                    )
                )
            
            response_text = self._format_live_status(status_data)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=response_text,
                    inline_keyboards=keyboard_builder.train_live_status(train_no)
                )
            )
        except Exception as e:
            logger.error(f"Error in train live status: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))

    def _extract_train_no(self, pnr_data: Dict) -> Optional[str]:
        """Extract train number from PNR data."""
        train_info = pnr_data.get("train", "") or pnr_data.get("train_no", "")
        if not train_info:
            return None
        
        # Often format is "12626 - KERALA EXPRESS"
        if isinstance(train_info, str) and " - " in train_info:
            return train_info.split(" - ")[0].strip()
        return str(train_info)

    def _format_live_status(self, data: Any) -> str:
        """Format live status data into a readable message."""
        # This assumes data is LiveStatusResult or similar
        # For mock/now, let's use dict access if it's a dict
        if hasattr(data, "data") and data.data:
            d = data.data
        elif isinstance(data, dict):
            d = data
        else:
            return "📡 <b>Live Status</b>\n\nStatus information received but could not be parsed."

        train_name = d.get("train_name", "Express")
        train_no = d.get("train_number", d.get("train_no", "N/A"))
        current_station = d.get("current_station", "Unknown")
        status = d.get("status", "On Time")
        delay = d.get("delay", "No delay")
        last_updated = d.get("last_updated", datetime.now().strftime("%H:%M"))

        return f"""📡 <b>Live Running Status</b>

🚂 <b>{train_no} - {train_name}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
📍 Current Location: <b>{current_station}</b>
🚦 Status: <b>{status}</b>
🕒 Delay: <b>{delay}</b>

Last Updated: <i>{last_updated}</i>
━━━━━━━━━━━━━━━━━━━━━━━━
<i>Powered by RouteMaster Intelligence</i>"""


class PNRHandler:
    """Handles PNR status and booking queries."""
    
    def __init__(self):
        self.live_handler = LiveStatusHandler()

    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle PNR requests.
        
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
            # Extract PNR number
            pnr = entities.get("pnr", "")
            
            if pnr:
                # Check specific PNR
                return await self._check_pnr_status(chat_id, pnr, context)
            elif intent_result.intent == IntentType.CHECK_PNR:
                # User wants to check PNR but didn't provide it
                from ..flow_handler import flow_handler
                from ..schemas import UserState
                context.data["flow_step_idx"] = 0
                context.data["flow_waiting_input"] = False
                context.state = UserState.PNR_INPUT
                return await flow_handler.handle_flow("", context, chat_id)
            else:
                # Show user's bookings (VIEW_BOOKINGS intent)
                return await self._show_user_bookings(chat_id, context)
                
        except Exception as e:
            logger.error(f"Error in PNR handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _check_pnr_status(
        self,
        chat_id: int,
        pnr: str,
        context: UserContext
    ) -> HandlerResult:
        """Check PNR status."""
        try:
            # Get PNR status from service
            pnr_data = await self._get_pnr_details(pnr)
            
            if not pnr_data:
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"❌ <b>PNR Not Found</b>\n\nPNR <code>{pnr}</code> not found in our system."
                    )
                )
            
            # Format PNR response
            if not pnr_data or pnr_data.get("status") == "N/A" or not pnr_data.get("train_no"):
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"❌ <b>Invalid PNR</b>\n\nCould not fetch valid data for PNR <code>{pnr}</code>."
                    )
                )

            response_text = self._format_pnr_status(pnr_data)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=response_text,
                    inline_keyboards=keyboard_builder.pnr_status(pnr)
                ),
                data={"current_pnr": pnr, "pnr_data": pnr_data}
            )
            
        except Exception as e:
            logger.error(f"Error checking PNR {pnr}: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error checking PNR</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _show_user_bookings(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show user's bookings."""
        try:
            # Get user bookings
            bookings = await self._get_user_bookings(chat_id)
            
            if not bookings:
                text = """📜 <b>My Bookings</b>

━━━━━━━━━━━━━━━━━━━━━━━━

You have no bookings yet.

🔍 <b>Search for trains</b> and book your first ticket!

<i>Tap 🔍 Search Trains to begin</i>"""
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=text,
                        keyboard=keyboard_builder.search_menu()
                    ),
                    next_state="idle"
                )
            
            # Format bookings
            response_text = self._format_bookings(bookings)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=response_text,
                    inline_keyboards=self._create_booking_keyboards(bookings)
                ),
                data={"bookings": bookings}
            )
            
        except Exception as e:
            logger.error(f"Error fetching bookings: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error fetching bookings</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _get_pnr_details(self, pnr: str) -> Optional[Dict[str, Any]]:
        """Get PNR details from service."""
        try:
            from services.booking.pnr import pnr_service
            
            pnr_data = await pnr_service.get_pnr_status(pnr)
            if not pnr_data:
                return self._get_mock_pnr_data(pnr)
            return pnr_data
            
        except Exception as e:
            logger.error(f"Error getting PNR details: {e}")
            # Return mock data for development
            return self._get_mock_pnr_data(pnr)
    
    async def _get_user_bookings(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get user's bookings."""
        try:
            from services.booking_service import booking_service
            
            # Get user from chat_id
            bookings = await booking_service.get_user_bookings(
                telegram_chat_id=str(chat_id)
            )
            return bookings
            
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}")
            # Return mock data for development
            return self._get_mock_bookings()
    
    def _format_pnr_status(self, pnr_data: Dict[str, Any]) -> str:
        """Format PNR status for display."""
        pnr = pnr_data.get("pnr", "N/A")
        train_no = pnr_data.get("train_no", "N/A")
        train_name = pnr_data.get("train_name", "Express")
        from_station = pnr_data.get("from_station", "N/A")
        to_station = pnr_data.get("to_station", "N/A")
        journey_date = pnr_data.get("journey_date", "N/A")
        departure = pnr_data.get("departure", "N/A")
        arrival = pnr_data.get("arrival", "N/A")
        class_type = pnr_data.get("class", "N/A")
        status = pnr_data.get("status", "N/A")
        chart_status = pnr_data.get("chart_status", "N/A")
        
        # Passenger details
        passengers = pnr_data.get("passengers", [])
        
        text = f"""📜 <b>PNR Status</b>

<code>{pnr}</code>

━━━━━━━━━━━━━━━���━━━━━━━━
<b>Train:</b> {train_no} - {train_name}
<b>Date:</b> {journey_date}
<b>Class:</b> {class_type}

<b>{from_station}</b> → <b>{to_station}</b>
{departure} → {arrival}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Status:</b> {status}
<b>Chart:</b> {chart_status}
"""
        
        if passengers:
            text += "\n<b>Passengers:</b>\n"
            for i, p in enumerate(passengers, 1):
                text += f"{i}. {p.get('name', 'N/A')} - {p.get('status', 'N/A')}\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━"
        
        return text
    
    def _format_bookings(self, bookings: List[Dict[str, Any]]) -> str:
        """Format bookings list for display."""
        text = f"""📜 <b>My Bookings</b> ({len(bookings)})

━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        for i, booking in enumerate(bookings, 1):
            pnr = booking.get("pnr", "N/A")
            train_no = booking.get("train_no", "N/A")
            train_name = booking.get("train_name", "Express")[:25]
            journey_date = booking.get("journey_date", "N/A")
            status = booking.get("status", "N/A")
            
            text += f"""<b>{i}. {train_no} - {train_name}</b>
📅 {journey_date} | PNR: <code>{pnr}</code>
Status: {status}

"""
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "Tap a booking for details."
        
        return text
    
    def _create_booking_keyboards(
        self, 
        bookings: List[Dict[str, Any]]
    ) -> List[List[Dict[str, str]]]:
        """Create inline keyboards for bookings."""
        keyboards = []
        
        for booking in bookings[:5]:
            pnr = booking.get("pnr", "")
            train_no = booking.get("train_no", "")
            keyboards.append([
                {
                    "text": f"📜 {train_no} - {pnr}",
                    "callback_data": f"booking_{pnr}"
                }
            ])
        
        # Add action buttons
        keyboards.append([
            {"text": "🔍 New Search", "callback_data": "search_new"},
            {"text": "🏠 Main Menu", "callback_data": "main_menu"}
        ])
        
        return keyboards
    
    def _get_mock_pnr_data(self, pnr: str) -> Dict[str, Any]:
        """Get mock PNR data for development."""
        return {
            "pnr": pnr,
            "train_no": "12951",
            "train_name": "Mumbai Rajdhani",
            "from_station": "Mumbai Central",
            "to_station": "New Delhi",
            "journey_date": "25-04-2026",
            "departure": "16:55",
            "arrival": "08:35",
            "class": "AC 3-Tier (3A)",
            "status": "CNF",
            "chart_status": "CHART PREPARED",
            "passengers": [
                {"name": "John Doe", "status": "CNF/B3/45"},
                {"name": "Jane Doe", "status": "CNF/B3/46"}
            ]
        }
    
    def _get_mock_bookings(self) -> List[Dict[str, Any]]:
        """Get mock bookings for development."""
        return [
            {
                "pnr": "1234567890",
                "train_no": "12951",
                "train_name": "Mumbai Rajdhani",
                "journey_date": "25-04-2026",
                "status": "Confirmed"
            },
            {
                "pnr": "9876543210",
                "train_no": "12909",
                "train_name": "Garib Rath",
                "journey_date": "30-04-2026",
                "status": "Waiting"
            }
        ]
    
    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle inline callback queries."""
        try:
            action, value = callback_data.split("_", 1) if "_" in callback_data else (callback_data, "")
            
            if action == "pnr":
                # Refresh PNR status
                return await self._check_pnr_status(chat_id, value, context)
            
            elif action == "refresh" and "pnr" in value:
                pnr = value.replace("pnr_", "")
                return await self._check_pnr_status(chat_id, pnr, context)

            elif action == "live" and "pnr" in value:
                pnr = value.replace("pnr_", "")
                return await self.live_handler.handle_pnr_live_status(chat_id, pnr)

            elif action == "booking":
                # Show booking details
                return await self._show_booking_details(chat_id, value)
            
            elif action == "pdf":
                # Download ticket PDF
                return await self._download_ticket(chat_id, value)
            
            elif action == "cancel_ticket":
                # Cancel booking
                return await self._cancel_booking(chat_id, value)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Processing..."
                )
            )
            
        except Exception as e:
            logger.error(f"Error in PNR callback: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )
    
    async def _show_booking_details(
        self,
        chat_id: int,
        pnr: str
    ) -> HandlerResult:
        """Show detailed booking information."""
        pnr_data = await self._get_pnr_details(pnr)
        
        if not pnr_data:
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Booking not found."
                )
            )
        
        response_text = self._format_pnr_status(pnr_data)
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=response_text,
                inline_keyboards=keyboard_builder.booking_details(pnr, pnr)
            ),
            data={"current_pnr": pnr, "pnr_data": pnr_data}
        )
    
    async def _download_ticket(
        self,
        chat_id: int,
        booking_id: str
    ) -> HandlerResult:
        """Download ticket PDF."""
        try:
            from services.booking_service import booking_service
            
            pdf_path = await booking_service.generate_telegram_ticket(booking_id)
            
            if pdf_path:
                success = await telegram_dispatcher.send_document(
                    chat_id=chat_id,
                    document_path=pdf_path,
                    caption="🎫 Your E-Ticket"
                )
                
                if success:
                    return HandlerResult(
                        status=HandlerResultStatus.SUCCESS,
                        response=BotResponse(
                            chat_id=chat_id,
                            text="✅ Ticket sent!"
                        )
                    )
            
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text="❌ Failed to generate ticket."
                )
            )
            
        except Exception as e:
            logger.error(f"Error downloading ticket: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )
    
    async def _cancel_booking(
        self,
        chat_id: int,
        booking_id: str
    ) -> HandlerResult:
        """Cancel a booking."""
        text = """❌ <b>Cancel Booking</b>

Are you sure you want to cancel this booking?

<i>Note: Cancellation charges may apply as per railway rules.</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "✅ Yes, Cancel", "callback_data": f"confirm_cancel_{booking_id}"},
                        {"text": "❌ No, Keep", "callback_data": f"keep_booking_{booking_id}"}
                    ]
                ]
            ),
            data={"cancelling_booking": booking_id}
        )


# Global instance
pnr_handler = PNRHandler()

# Setup PNR Input Flow
from ..flow_handler import flow_handler, Flow, FlowStep
from ..schemas import UserState

async def process_pnr_input(text: str, context: UserContext):
    # Strip whitespace and capture
    context.data["pending_pnr"] = text.strip()

async def complete_pnr_input(context: UserContext, chat_id: int):
    pnr = context.data.get("pending_pnr")
    return await pnr_handler._check_pnr_status(chat_id, pnr, context)

pnr_input_flow = Flow(
    name="PNR Input",
    state=UserState.PNR_INPUT,
    steps=[
        FlowStep(
            id="pnr_number",
            prompt="🎫 Please enter your 10-digit PNR number:",
            validator=lambda x: len(x.strip()) == 10 and x.strip().isdigit(),
            processor=process_pnr_input
        )
    ],
    on_complete=complete_pnr_input
)

flow_handler.register_flow(pnr_input_flow)
