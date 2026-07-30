"""
Profile Handler
===============
Handles user profile and account management.
"""

from telegram_bot.schemas import UserState
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
from database.session import get_db
from services.user_service import UserService
from services.booking_service import BookingService
from services.credit_service import UnlockCreditService
from database.models import User, CreditTransaction, Booking as BookingModel

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
            from database.session import SessionUser
            
            db = SessionUser()
            try:
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
            finally:
                db.close()
                    
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
                "add": self._add_funds,
                "gift": self._redeem_code,
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
        """Show real user statistics."""
        try:
            from database.session import SessionUser
            db = SessionUser()
            try:
                user_service = UserService(db)
                user = await user_service.get_user_by_telegram_id(str(chat_id))
                
                if not user:
                    return await self._handle_registration(chat_id, None)

                # Fetch real stats
                patterns = await user_service.analyze_travel_patterns(user.id)
                booking_service = BookingService(db)
                bookings, total_bookings = booking_service.get_user_bookings(user_id=user.id, limit=100)
                
                completed = sum(1 for b in bookings if b.booking_status == "confirmed")
                cancelled = sum(1 for b in bookings if b.booking_status == "cancelled")
                
                credit_service = UnlockCreditService()
                balance = credit_service.get_user_balance(db, user.id)

                text = f"""📊 <b>My Statistics</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🎫 <b>Total Bookings:</b> {total_bookings}
✅ <b>Completed:</b> {completed}
❌ <b>Cancelled:</b> {cancelled}

🚂 <b>Total Distance:</b> {patterns.total_distance_km:,} km
⏱️ <b>Favorite Class:</b> {patterns.preferred_class or "N/A"}

💰 <b>Karma Score:</b> {user.karma_score or 0}
💳 <b>Wallet Balance:</b> ₹{balance['total']:.2f}

🏆 <b>Badges Earned:</b>
{self._get_badges_text(user)}

━━━━━━━━━━━━━━━━━━━━━━━━"""
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=text,
                        inline_keyboards=[[{"text": "🔙 Back", "callback_data": "profile_back"}]]
                    )
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))

    def _get_badges_text(self, user: User) -> str:
        """Generate badges text based on user data."""
        badges = []
        if user.karma_score > 1000:
            badges.append("• Elite Traveler")
        if user.total_lifetime_credits > 50:
            badges.append("• Frequent Voyager")
        if not badges:
            badges.append("• Explorer (New)")
        return "\n".join(badges)
    
    async def _show_history(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show real booking history."""
        try:
            from database.session import SessionUser
            db = SessionUser()
            try:
                user_service = UserService(db)
                user = await user_service.get_user_by_telegram_id(str(chat_id))
                
                if not user:
                    return await self._handle_registration(chat_id, None)

                booking_service = BookingService(db)
                bookings, total = booking_service.get_user_bookings(user_id=user.id, limit=5)

                if not bookings:
                    text = "🎫 <b>Booking History</b>\n\nNo bookings found yet. Start your journey today!"
                else:
                    history_lines = []
                    for i, b in enumerate(bookings, 1):
                        date_str = b.travel_date.strftime("%d %b %Y") if b.travel_date else "N/A"
                        status_emoji = "✅" if b.booking_status == "confirmed" else "❌" if b.booking_status == "cancelled" else "⏳"
                        history_lines.append(f"{i}. {date_str} - {b.pnr_number}\n   {status_emoji} {b.booking_status.upper()}")
                    
                    text = f"""🎫 <b>Booking History</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Last {len(bookings)} Journeys:</b>

{chr(10).join(history_lines)}

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Tap a booking for details</i>"""
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=text,
                        inline_keyboards=[
                            [
                                {"text": "📜 View All on Web", "url": f"https://routemaster.io/profile/bookings"},
                                {"text": "🔙 Back", "callback_data": "profile_back"}
                            ]
                        ]
                    )
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error showing history: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))
    
    async def _show_wallet(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show real wallet and credit information."""
        try:
            from database.session import SessionUser
            db = SessionUser()
            try:
                user_service = UserService(db)
                user = await user_service.get_user_by_telegram_id(str(chat_id))
                
                if not user:
                    return await self._handle_registration(chat_id, None)

                credit_service = UnlockCreditService()
                balance = credit_service.get_user_balance(db, user.id)
                
                # Fetch recent credit transactions
                transactions = db.query(CreditTransaction).filter(
                    CreditTransaction.user_id == user.id
                ).order_by(CreditTransaction.timestamp.desc()).limit(4).all()

                tx_lines = []
                for tx in transactions:
                    icon = "✅" if tx.amount > 0 else "❌"
                    date_str = tx.timestamp.strftime("%b %d")
                    tx_lines.append(f"{icon} {tx.amount:+} ({date_str})\n   {tx.transaction_type}")

                text = f"""💳 <b>My Wallet</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Balance:</b> {balance['total']} Credits
<i>({balance['paid']} Paid, {balance['bonus']} Bonus)</i>

<b>Recent Activity:</b>

{chr(10).join(tx_lines) if tx_lines else "No recent transactions."}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>Quick Actions:</b>

• 💰 Buy Credits
• 🎁 Redeem Code
• 📜 View Full Ledger on Web

<i>1 Credit = 1 Route Unlock</i>"""
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=text,
                        inline_keyboards=[
                            [
                                {"text": "💰 Buy Credits", "callback_data": "wallet_add"},
                                {"text": "📜 History", "callback_data": "wallet_history"}
                            ],
                            [
                                {"text": "🎁 Redeem", "callback_data": "wallet_gift"},
                                {"text": "🔙 Back", "callback_data": "profile_back"}
                            ]
                        ]
                    )
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error showing wallet: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))
    
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
        """Edit profile details using the FlowHandler."""
        from ..flow_handler import flow_handler
        
        # Reset flow state
        context.data["flow_step_idx"] = 0
        context.data["flow_waiting_input"] = False
        
        # We need to set state to something unique for this flow so flow_handler picks it up
        from ..schemas import UserState
        context.state = UserState.PROFILE_EDIT
        
        # Start the flow
        return await flow_handler.handle_flow("", context, chat_id)

    async def _add_funds(self, chat_id: int, context: UserContext) -> HandlerResult:
        """Handle 'Buy Credits' flow."""
        text = """💰 <b>Buy RouteMaster Credits</b>

━━━━━━━━━━━━━━━━━━━━━━━━
Credits allow you to unlock <b>Pareto-Optimal</b> routes with deep safety analysis.

<b>Choose a Package:</b>

• <b>Starter:</b> 5 Credits @ ₹199
• <b>Pro:</b> 15 Credits @ ₹499 (Best Value)
• <b>Elite:</b> 50 Credits @ ₹999

<i>Click below to pay via UPI or Card:</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [{"text": "💳 Pay via Razorpay", "url": "https://routemaster.io/pay?credits=15"}],
                    [{"text": "🔙 Back to Wallet", "callback_data": "profile_wallet"}]
                ]
            )
        )

    async def _redeem_code(self, chat_id: int, context: UserContext) -> HandlerResult:
        """Handle 'Redeem Code' flow."""
        text = """🎁 <b>Redeem Gift Code</b>

━━━━━━━━━━━━━━━━━━━━━━━━
Please enter your 12-digit redemption code below.

<i>Example: RM-XXXX-XXXX-XXXX</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[[{"text": "🔙 Back", "callback_data": "profile_wallet"}]]
            )
        )


# Global instance
profile_handler = ProfileHandler()

# Setup Profile Edit Flow
from ..flow_handler import flow_handler, Flow, FlowStep
from ..schemas import UserState

async def save_profile_name(text: str, context: UserContext):
    context.data["edit_profile_name"] = text

async def save_profile_email(text: str, context: UserContext):
    context.data["edit_profile_email"] = text
    # In a real app, we would save to DB here
    
profile_edit_flow = Flow(
    name="Profile Edit",
    state=UserState.PROFILE_EDIT,
    steps=[
        FlowStep(
            id="name",
            prompt="✏️ Please enter your Full Name:",
            validator=lambda x: len(x) > 2,
            processor=save_profile_name
        ),
        FlowStep(
            id="email",
            prompt="📧 Please enter your Email Address:",
            validator=lambda x: "@" in x and "." in x,
            processor=save_profile_email
        )
    ]
)

flow_handler.register_flow(profile_edit_flow)
