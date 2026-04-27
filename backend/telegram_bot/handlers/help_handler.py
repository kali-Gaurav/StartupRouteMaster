"""
Help Handler
============
Handles help commands and provides user guidance.
"""

import logging
from typing import Dict, Any

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType
)
from ..command_router import HandlerResult, HandlerResultStatus
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder

logger = logging.getLogger(__name__)


class HelpHandler:
    """Handles help commands and user guidance."""
    
    HELP_MESSAGE = """
❓ <b>Help & Guide</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Available Commands:</b>

/start - Start the bot
/help - Show this help
/search - Search for trains
/book - Book a ticket
/bookings - View my bookings
/pnr - Check PNR status
/profile - My profile
/wallet - Wallet & payments
/sos - Emergency assistance

━━━━━━━━━━━━━━━━━━━━━━━━
<b>How to Search Trains:</b>

🔍 Just type naturally:
• "Trains from Mumbai to Delhi"
• "Trains to Bangalore from Chennai"
• "Trains on 25-04-2026"
• "12951 schedule"

━━━━━━━━━━━━━━━━━━━━━━━━
<b>How to Book:</b>

1. Search for trains
2. Select a train
3. Choose class & quota
4. Add passenger details
5. Review & pay

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Tips:</b>

💡 Use inline buttons for faster actions
💡 Share location for SOS emergencies
💡 Check PNR for real-time status
💡 Enable notifications for alerts

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Need More Help?</b>

📞 Railway Helpline: 139
📧 Email: support@example.com

<i>Tap an option below</i>
"""
    
    SEARCH_HELP = """
🔍 <b>How to Search Trains</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Search by Route:</b>
• "Trains from Mumbai to Delhi"
• "Delhi to Bangalore trains"
• "Trains between Howrah and Chennai"

<b>Search by Train:</b>
• "Train 12951"
• "Mumbai Rajdhani schedule"
• " Garib Rath"

<b>Search by Date:</b>
• "Trains on 25-04-2026"
• "Trains tomorrow"
• "Trains day after"

<b>Combined Search:</b>
• "Trains from Mumbai to Delhi on 25-04-2026"

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Tip: You can also use station codes like "NDLS" for New Delhi</i>
"""
    
    BOOKING_HELP = """
🎫 <b>How to Book Tickets</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Step 1: Search</b>
Find trains using the search command

<b>Step 2: Select Train</b>
Choose from available options

<b>Step 3: Choose Class</b>
• 1A - AC First Class
• 2A - AC 2-Tier
• 3A - AC 3-Tier
• CC - AC Chair Car
• SL - Sleeper
• 2S - Second Sitting

<b>Step 4: Select Quota</b>
• General
• Tatkal
• Ladies
• Senior Citizen

<b>Step 5: Add Passengers</b>
Enter name, age, gender

<b>Step 6: Pay</b>
Wallet, Card, UPI, Net Banking

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Booking timeout: 15 minutes</i>
"""
    
    PAYMENT_HELP = """
💳 <b>Payment Options</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Wallet:</b>
• Instant payment
• Balance required
• Cashback available

<b>Card:</b>
• Credit/Debit cards
• Visa, Mastercard, RuPay
• EMI options available

<b>UPI:</b>
• Google Pay, PhonePe
• BHIM, Paytm
• Instant transfer

<b>Net Banking:</b>
• All major banks
• Secure banking

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Refund Policy:</b>
• Cancellation charges apply
• Refund to original payment
• Processing: 3-5 days

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    FAQ_ANSWERS = {
        "cancellation": """
❓ <b>Cancellation Policy</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Refund Timeline:</b>
• Before chart prep: 80-90% refund
• After chart prep: No refund
• Tatkal: No refund

<b>How to Cancel:</b>
1. Go to My Bookings
2. Select booking
3. Tap Cancel
4. Confirm

<b>Note:</b>
• Partial cancellation not allowed
• All passengers will be cancelled
""",
        "pnr": """
❓ <b>About PNR</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>What is PNR?</b>
PNR (Passenger Name Record) is a 10-digit number that contains your booking details.

<b>How to Check:</b>
• Type "Check PNR 1234567890"
• Or use /pnr command

<b>PNR Status Meanings:</b>
• CNF - Confirmed
• RAC - Reservation Against Cancellation
• WL - Waiting List
• GNWL - General Waiting List

<b>Chart Preparation:</b>
Usually 4 hours before departure
""",
        "refund": """
❓ <b>Refund & Cancellation</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Cancellation Charges:</b>

<b>AC Classes:</b>
• 1A: ₹120 + 25% of fare
• 2A: ₹120 + 25% of fare
• 3A: ₹100 + 25% of fare

<b>Non-AC Classes:</b>
• CC: ₹60 + 25% of fare
• SL: ₹60 + 25% of fare
• 2S: ₹30 + 25% of fare

<b>Refund Timeline:</b>
3-5 business days

<b>Note:</b>
Tatkal tickets cannot be cancelled
""",
        "delay": """
❓ <b>Train Delays</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>How to Check Delay:</b>
• "Train 12951 status"
• "Is my train delayed"
• Check PNR for delay info

<b>Delay Compensation:</b>
• > 1 hour delay: 50% refund
• > 2 hours delay: Full refund

<b>Alternative Options:</b>
• Check alternative trains
• Request for RAC if available
""",
        "account": """
❓ <b>Account & Profile</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Creating Account:</b>
• Phone number verification
• Email optional
• Telegram linked automatically

<b>Managing Profile:</b>
• Update name, email, phone
• Add profile picture
• Set preferences

<b>Security:</b>
• 2FA available
• Login alerts
• Session management
"""
    }
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle help requests.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        text = (message.text or "").lower()
        
        try:
            # Check for specific help topics
            if "search" in text:
                return await self._show_search_help(chat_id)
            elif "book" in text:
                return await self._show_booking_help(chat_id)
            elif "payment" in text or "wallet" in text:
                return await self._show_payment_help(chat_id)
            elif "cancel" in text or "refund" in text:
                return await self._show_faq(chat_id, "cancellation")
            elif "pnr" in text:
                return await self._show_faq(chat_id, "pnr")
            elif "delay" in text:
                return await self._show_faq(chat_id, "delay")
            elif "account" in text or "profile" in text:
                return await self._show_faq(chat_id, "account")
            else:
                # General help
                return await self._show_general_help(chat_id)
                
        except Exception as e:
            logger.error(f"Error in help handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _show_general_help(self, chat_id: int) -> HandlerResult:
        """Show general help."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=self.HELP_MESSAGE,
                inline_keyboards=keyboard_builder.help_menu()
            ),
            next_state="help"
        )
    
    async def _show_search_help(self, chat_id: int) -> HandlerResult:
        """Show search help."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=self.SEARCH_HELP,
                inline_keyboards=[
                    [
                        {"text": "🔍 Search Now", "callback_data": "help_search_now"},
                        {"text": "❓ More Help", "callback_data": "help_main"}
                    ]
                ]
            ),
            next_state="help"
        )
    
    async def _show_booking_help(self, chat_id: int) -> HandlerResult:
        """Show booking help."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=self.BOOKING_HELP,
                inline_keyboards=[
                    [
                        {"text": "🎫 Book Now", "callback_data": "help_book_now"},
                        {"text": "❓ More Help", "callback_data": "help_main"}
                    ]
                ]
            ),
            next_state="help"
        )
    
    async def _show_payment_help(self, chat_id: int) -> HandlerResult:
        """Show payment help."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=self.PAYMENT_HELP,
                inline_keyboards=[
                    [
                        {"text": "💳 My Wallet", "callback_data": "help_wallet"},
                        {"text": "❓ More Help", "callback_data": "help_main"}
                    ]
                ]
            ),
            next_state="help"
        )
    
    async def _show_faq(self, chat_id: int, topic: str) -> HandlerResult:
        """Show FAQ answer."""
        faq_text = self.FAQ_ANSWERS.get(topic, self.HELP_MESSAGE)
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=faq_text,
                inline_keyboards=[
                    [
                        {"text": "❓ Other Questions", "callback_data": "help_main"},
                        {"text": "📞 Contact Support", "callback_data": "help_support"}
                    ]
                ]
            ),
            next_state="help"
        )
    
    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle help callbacks."""
        try:
            action = callback_data.replace("help_", "")
            
            handlers = {
                "search": self._show_search_help,
                "booking": self._show_booking_help,
                "payments": self._show_payment_help,
                "faq": lambda cid: self._show_faq(cid, "cancellation"),
                "support": self._show_support,
                "main": self._show_general_help,
                "search_now": self._redirect_to_search,
                "book_now": self._redirect_to_booking,
            }
            
            handler = handlers.get(action)
            if handler:
                return await handler(chat_id)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Processing..."
                )
            )
            
        except Exception as e:
            logger.error(f"Error in help callback: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )
    
    async def _show_support(self, chat_id: int) -> HandlerResult:
        """Show support information."""
        text = """📞 <b>Contact Support</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Railway Helpline:</b>
📞 139 (24/7)

<b>Email:</b>
📧 support@example.com

<b>Response Time:</b>
• Email: 24-48 hours
• Chat: Immediate

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Before Contacting:</b>

✅ Check FAQ first
✅ Have PNR ready
✅ Note booking ID
✅ Describe issue clearly

<i>We typically respond within 24 hours.</i>
"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "📞 Call 139", "url": "tel:139"},
                        {"text": "✉️ Email Us", "callback_data": "help_email"}
                    ],
                    [
                        {"text": "🔙 Back", "callback_data": "help_main"}
                    ]
                ]
            )
        )
    
    async def _redirect_to_search(self, chat_id: int) -> HandlerResult:
        """Redirect to search."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text="🔍 <b>Search Trains</b>\n\nEnter your travel details:\n\n<i>Example: Trains from Mumbai to Delhi</i>",
                keyboard={
                    "keyboard": [
                        [{"text": "🔍 Search Trains"}],
                        [{"text": "🔙 Back"}]
                    ],
                    "resize_keyboard": True
                }
            ),
            next_state="searching"
        )
    
    async def _redirect_to_booking(self, chat_id: int) -> HandlerResult:
        """Redirect to booking."""
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text="🎫 <b>Book Tickets</b>\n\nSearch for trains first, then book your ticket.",
                keyboard=keyboard_builder.search_menu()
            ),
            next_state="booking"
        )


# Global instance
help_handler = HelpHandler()