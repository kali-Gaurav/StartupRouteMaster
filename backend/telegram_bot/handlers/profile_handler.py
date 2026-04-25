"""
Profile Handler
===============
Handles user profile and account management.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType, HandlerResult, HandlerResultStatus
)
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder
from ..user_session_manager import user_session_manager

logger = logging.getLogger(__name__)


class ProfileHandler:
    """Handles user profile and account operations."""
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle profile requests.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        text = message.text or ""
        
        try:
            # Get user profile
            profile = await self._get_user_profile(chat_id, message.from_user)
            
            if not profile:
                # User not registered
                return await self._handle_registration(chat_id, message.from_user)
            
            # Show profile menu
            return await self._show_profile_menu(chat_id, profile, context)
            
        except Exception as e:
            logger.error(f"Error in profile handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _get_user_profile(
        self,
        chat_id: int,
        telegram_user
    ) -> Optional[Dict[str, Any]]:
        """Get user profile from database."""
        try:
            from services.user_service import UserService
            from database.config import get_db
            
            async with get_db() as db:
                user_service = UserService(db)
                
                # Try to find user by Telegram ID
                user = await user_service.get_user_by_telegram_id(str(chat_id))
                
                if user:
                    return {
                        "id": user.id,
                        "name": user.full_name or telegram_user.first_name,
                        "email": user.email,
                        "phone": user.phone_number,
                        "is_verified": user.is_verified,
                        "created_at": user.created_at
                    }
                    
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
        
        return None
    
    async def _handle_registration(
        self,
        chat_id: int,
        telegram_user
    ) -> HandlerResult:
        """Handle new user registration."""
        text = f"""👤 <b>Welcome, {telegram_user.first_name}!</b>

To use all features, please link your account.

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Options:</b>

1️⃣ <b>Login with Phone</b>
   Get OTP on your registered mobile

2️⃣ <b>Quick Register</b>
   Create account with phone number

3️⃣ <b>Continue as Guest</b>
   Limited features available

<i>Your Telegram profile will be linked automatically.</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "📱 Login with Phone", "callback_data": "reg_phone"},
                        {"text": "⚡ Quick Register", "callback_data": "reg_quick"}
                    ],
                    [
                        {"text": "👤 Continue as Guest", "callback_data": "reg_guest"}
                    ]
                ]
            ),
            next_state="profile",
            data={"profile_step": "registration"}
        )
    
    async def _show_profile_menu(
        self,
        chat_id: int,
        profile: Dict[str, Any],
        context: UserContext
    ) -> HandlerResult:
        """Show profile menu."""
        name = profile.get("name", "Traveler")
        email = profile.get("email", "Not set")
        phone = profile.get("phone", "Not set")
        verified = "✅" if profile.get("is_verified") else "❌"
        
        text = f"""👤 <b>My Profile</b>

<b>{name}</b> {verified}

━━━━━━━━━━━━━━━━━━━━━━━━
📧 <b>Email:</b> {email}
📱 <b>Phone:</b> {phone}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Actions:</b>

• 📊 View Statistics
• 🎫 Booking History
• 💳 Wallet Balance
• ⚙️ Settings

<i>Tap an option to continue</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=self._get_profile_keyboards()
            ),
            next_state="profile",
            data={"profile_data": profile}
        )
    
    def _get_profile_keyboards(self) -> list:
        """Get profile inline keyboards."""
        return [
            [
                {"text": "📊 My Stats", "callback_data": "profile_stats"},
                {"text": "🎫 History", "callback_data": "profile_history"}
            ],
            [
                {"text": "💳 Wallet", "callback_data": "profile_wallet"},
                {"text": "⚙️ Settings", "callback_data": "profile_settings"}
            ],
            [
                {"text": "✏️ Edit Profile", "callback_data": "profile_edit"},
                {"text": "🔙 Back", "callback_data": "profile_back"}
            ]
        ]
    
    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle profile callbacks."""
        try:
            action = callback_data.split("_")[1] if "_" in callback_data else callback_data
            
            handlers = {
                "stats": self._show_stats,
                "history": self._show_history,
                "wallet": self._show_wallet,
                "settings": self._show_settings,
                "edit": self._edit_profile,
            }
            
            handler = handlers.get(action)
            if handler:
                return await handler(chat_id, context)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Processing..."
                )
            )
            
        except Exception as e:
            logger.error(f"Error in profile callback: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )
    
    async def _show_stats(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show user statistics."""
        text = """📊 <b>My Statistics</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🎫 <b>Total Bookings:</b> 12
✅ <b>Completed:</b> 10
❌ <b>Cancelled:</b> 2

🚂 <b>Total Distance:</b> 5,420 km
⏱️ <b>Total Travel Time:</b> 82 hours

💰 <b>Total Spent:</b> ₹45,680
💳 <b>Wallet Balance:</b> ₹1,250

🏆 <b>Badges Earned:</b>
• First Journey (Jan 2025)
• 10 Trips (Mar 2025)
• Frequent Traveler (Apr 2025)

━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[[{"text": "🔙 Back", "callback_data": "profile_back"}]]
            )
        )
    
    async def _show_history(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show booking history."""
        text = """🎫 <b>Booking History</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Last 5 Journeys:</b>

1. 20 Apr 2026 - Mumbai → Delhi
   12951 Mumbai Rajdhani | CNF

2. 15 Apr 2026 - Delhi → Jaipur
   12982 Udyog Express | CNF

3. 10 Apr 2026 - Bangalore → Chennai
   12608 Lalbagh Express | CNF

4. 05 Apr 2026 - Chennai → Hyderabad
   12759 Charminar Exp | Cancelled

5. 28 Mar 2026 - Hyderabad → Bangalore
   12737 Gowthami Exp | CNF

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Tap a booking for details</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "📜 View All", "callback_data": "history_all"},
                        {"text": "🔙 Back", "callback_data": "profile_back"}
                    ]
                ]
            )
        )
    
    async def _show_wallet(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show wallet information."""
        text = """💳 <b>My Wallet</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Balance:</b> ₹1,250.00

<b>Recent Transactions:</b>

✅ +₹2,000 (Apr 15)
   Wallet Top-up

✅ +₹500 (Apr 10)
   Refund - Booking #12345

❌ -₹1,250 (Apr 05)
   Booking #12340

✅ +₹800 (Apr 01)
   Refund - Booking #12335

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Actions:</b>

• 💰 Add Money
• 🎁 Gift Voucher
• 📜 Transaction History

<i>Minimum top-up: ₹100</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "💰 Add Money", "callback_data": "wallet_add"},
                        {"text": "📜 History", "callback_data": "wallet_history"}
                    ],
                    [
                        {"text": "🎁 Gift Voucher", "callback_data": "wallet_gift"},
                        {"text": "🔙 Back", "callback_data": "profile_back"}
                    ]
                ]
            )
        )
    
    async def _show_settings(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show settings menu."""
        text = """⚙️ <b>Settings</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Notifications:</b>

🔔 PNR Alerts: ✅ ON
🔔 Delay Alerts: ✅ ON
🔔 Cancellation Alerts: ✅ ON
🔔 Promotional: ❌ OFF

<b>Preferences:</b>

🌐 Language: English
📅 Date Format: DD-MM-YYYY
💱 Currency: INR (₹)

<b>Security:</b>

🔒 2FA: ❌ OFF
📱 Login Alert: ✅ ON

━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [
                        {"text": "🔔 Notifications", "callback_data": "settings_notif"},
                        {"text": "🌐 Language", "callback_data": "settings_lang"}
                    ],
                    [
                        {"text": "🔒 Security", "callback_data": "settings_sec"},
                        {"text": "🔙 Back", "callback_data": "profile_back"}
                    ]
                ]
            )
        )
    
    async def _edit_profile(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Edit profile details."""
        text = """✏️ <b>Edit Profile</b>

━━━━━━━━━━━━━━━━━━━━━━━━
What would you like to update?

• 👤 Name
• 📧 Email
• 📱 Phone
• 🔑 Password

<i>Enter the field name to update</i>

Example: <i>"Update email to new@email.com"</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard_builder.back_only()
            ),
            next_state="profile_editing",
            data={"profile_step": "edit"}
        )


# Global instance
profile_handler = ProfileHandler()