"""
Telegram Bot Service - Linking, state management, and booking integration.
Handles user authentication linking and conversation flow.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import User, TelegramConversationState, Booking, PassengerDetails
from database.models.telegram import TelegramBookingLink

logger = logging.getLogger("telegram_service")


class TelegramService:
    """Service for Telegram bot user management and booking integration."""

    def __init__(self, db: Session):
        self.db = db

    async def create_auth_link(
        self,
        telegram_user_id: str,
        telegram_username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create one-time authentication link for user to link Telegram account.

        Args:
            telegram_user_id: Telegram user ID (from Telegram Bot API)
            telegram_username: Telegram @username (optional)

        Returns:
            {
                "link_token": "uuid",
                "expires_in_seconds": 3600,
                "auth_url": "https://app.routemaster.com/telegram/link?token=uuid"
            }
        """
        link_token = str(uuid4())
        link_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        try:
            # Check if this telegram_user_id is already linked
            existing_state = self.db.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.telegram_user_id == telegram_user_id
                )
            ).scalar_one_or_none()

            if existing_state:
                # Reset auth link
                existing_state.context = {
                    **(existing_state.context or {}),
                    "auth_link_token": link_token,
                    "auth_link_expiry": link_expiry.isoformat(),
                }
                existing_state.current_state = "AWAITING_AUTHENTICATION"
            else:
                # Create new conversation state
                existing_state = TelegramConversationState(
                    telegram_user_id=telegram_user_id,
                    current_state="AWAITING_AUTHENTICATION",
                    context={
                        "auth_link_token": link_token,
                        "auth_link_expiry": link_expiry.isoformat(),
                        "telegram_username": telegram_username,
                    }
                )
                self.db.add(existing_state)

            self.db.commit()
            logger.info(f"Created auth link for telegram_user {telegram_user_id}")

            return {
                "link_token": link_token,
                "expires_in_seconds": 3600,
                "auth_url": f"https://app.routemaster.com/telegram/link?token={link_token}",
                "message": "Click the link above to link your Telegram account to RouteMaster"
            }

        except Exception as e:
            logger.error(f"Error creating auth link: {e}")
            raise

    async def confirm_telegram_link(
        self,
        link_token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Complete linking of Telegram account to User account.

        Args:
            link_token: One-time token from auth_link
            user_id: RouteMaster User ID

        Returns:
            {
                "success": bool,
                "message": str,
                "user": {...}
            }
        """
        try:
            # Find conversation state with this token
            conv_state = self.db.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.context["auth_link_token"].astext == link_token
                )
            ).scalar_one_or_none()

            if not conv_state:
                return {
                    "success": False,
                    "message": "Invalid or expired link token"
                }

            # Check token expiry
            expiry_str = conv_state.context.get("auth_link_expiry")
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.now(timezone.utc) > expiry:
                    return {
                        "success": False,
                        "message": "Link token has expired"
                    }

            # Get user
            user = self.db.get(User, user_id)
            if not user:
                return {
                    "success": False,
                    "message": "User not found"
                }

            # Link accounts
            user.telegram_id = conv_state.telegram_user_id
            conv_state.user_id = user_id
            conv_state.current_state = "IDLE"
            conv_state.context = {
                **(conv_state.context or {}),
                "linked_at": datetime.now(timezone.utc).isoformat(),
                "auth_link_token": None,  # Clear token after use
            }

            self.db.commit()
            logger.info(f"Linked telegram_user {conv_state.telegram_user_id} to user {user_id}")

            return {
                "success": True,
                "message": f"✅ Telegram account linked! Welcome, {user.full_name or 'User'}!",
                "user": {
                    "id": user.id,
                    "name": user.full_name,
                    "email": user.email,
                }
            }

        except Exception as e:
            logger.error(f"Error confirming telegram link: {e}")
            return {
                "success": False,
                "message": f"Error linking account: {str(e)}"
            }

    async def complete_booking(
        self,
        link_token: str,
        passenger_name: str,
        passenger_age: int,
        passenger_gender: str,
        seat_preference: Optional[str] = None,
        berth_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete booking via Telegram after payment verification.

        Args:
            link_token: Token from TelegramBookingLink
            passenger_name: Full name of passenger
            passenger_age: Age
            passenger_gender: Gender (M/F/Other)
            seat_preference: Seat preference
            berth_preference: Berth preference (Upper/Middle/Lower/Any)

        Returns:
            {
                "success": bool,
                "booking_id": str,
                "pnr": str,
                "message": str,
                "error": str (if failed)
            }
        """
        try:
            # Find booking link
            booking_link = self.db.execute(
                select(TelegramBookingLink).where(
                    TelegramBookingLink.link_token == link_token
                )
            ).scalar_one_or_none()

            if not booking_link:
                return {
                    "success": False,
                    "error": "Booking link not found"
                }

            if booking_link.is_used:
                return {
                    "success": False,
                    "error": "This booking link has already been used"
                }

            if booking_link.expires_at and datetime.now(timezone.utc) > booking_link.expires_at:
                return {
                    "success": False,
                    "error": "Booking link has expired"
                }

            # Get user via conversation state
            conv_state = self.db.execute(
                select(TelegramConversationState).where(
                    TelegramConversationState.telegram_user_id == str(booking_link.telegram_user_id)
                )
            ).scalar_one_or_none()

            if not conv_state or not conv_state.user_id:
                return {
                    "success": False,
                    "error": "User account not linked to Telegram"
                }

            user = self.db.get(User, conv_state.user_id)

            # Create booking
            booking = Booking(
                user_id=user.id,
                train_number=booking_link.train_number,
                from_station_code=booking_link.source,
                to_station_code=booking_link.destination,
                travel_date=datetime.strptime(booking_link.travel_date, "%Y-%m-%d").date(),
                class_type=booking_link.train_class,
                booking_status="confirmed",
                payment_status="completed",
                berth_preference=berth_preference,
            )
            self.db.add(booking)
            self.db.flush()

            # Add passenger details
            passenger = PassengerDetails(
                booking_id=booking.id,
                full_name=passenger_name,
                age=passenger_age,
                gender=passenger_gender,
                berth_preference=berth_preference,
            )
            self.db.add(passenger)

            # Mark booking link as used
            booking_link.is_used = True
            booking_link.used_at = datetime.now(timezone.utc)
            booking_link.booking_id = booking.id

            self.db.commit()
            logger.info(f"Booking completed via Telegram: {booking.id}")

            return {
                "success": True,
                "booking_id": booking.id,
                "pnr": booking.pnr_number,
                "message": f"✅ Booking confirmed! PNR: {booking.pnr_number}"
            }

        except Exception as e:
            logger.error(f"Error completing booking: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": f"Booking failed: {str(e)}"
            }

    async def get_conversation_state(
        self,
        telegram_user_id: str
    ) -> Optional[TelegramConversationState]:
        """Get or create conversation state for user."""
        state = self.db.execute(
            select(TelegramConversationState).where(
                TelegramConversationState.telegram_user_id == telegram_user_id
            )
        ).scalar_one_or_none()

        if not state:
            state = TelegramConversationState(
                telegram_user_id=telegram_user_id,
                current_state="IDLE"
            )
            self.db.add(state)
            self.db.commit()

        return state

    async def update_conversation_state(
        self,
        telegram_user_id: str,
        new_state: str,
        context_update: Optional[Dict[str, Any]] = None
    ) -> TelegramConversationState:
        """Update conversation state and context."""
        state = await self.get_conversation_state(telegram_user_id)
        state.current_state = new_state
        state.last_message_at = datetime.now(timezone.utc)
        state.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        if context_update:
            state.context = {
                **(state.context or {}),
                **context_update
            }

        self.db.commit()
        return state

    async def cleanup_expired_conversations(self) -> int:
        """Clean up expired conversation states. Returns count deleted."""
        expired = self.db.execute(
            select(TelegramConversationState).where(
                TelegramConversationState.expires_at < datetime.now(timezone.utc)
            )
        ).scalars().all()

        count = len(expired)
        for state in expired:
            self.db.delete(state)

        self.db.commit()
        logger.info(f"Cleaned up {count} expired conversation states")
        return count


# Singleton instance
_telegram_service = None


def get_telegram_service(db: Session) -> TelegramService:
    """Get or create telegram service instance."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService(db)
    return _telegram_service
