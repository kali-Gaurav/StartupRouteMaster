"""
Telegram Active Notification Manager
====================================
Handles asynchronous notifications for PNR status, SOS alerts, and tracking.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from .dispatcher import telegram_dispatcher
from .user_session_manager import user_session_manager
from .keyboards import keyboard_builder

logger = logging.getLogger(__name__)

class ActiveNotificationManager:
    """
    Manages real-time notifications to users.
    Used by background workers to alert users about PNR changes, 
    delays, or safety alerts.
    """
    
    async def notify_pnr_update(
        self, 
        chat_id: int, 
        pnr: str, 
        old_status: str, 
        new_status: str,
        train_info: Optional[str] = None
    ):
        """Notify user about PNR status change."""
        text = f"🔔 <b>PNR Status Update</b>\n\n"
        text += f"PNR: <code>{pnr}</code>\n"
        if train_info:
            text += f"Train: <b>{train_info}</b>\n"
        text += f"Status: {old_status} ➔ <b>{new_status}</b>\n\n"
        
        if "CNF" in new_status:
            text += "✅ Your ticket is now <b>Confirmed</b>! Happy Journey!"
        
        await telegram_dispatcher.send_message(
            chat_id=chat_id,
            text=text,
            inline_keyboard=keyboard_builder.pnr_status(pnr)
        )
        logger.info(f"PNR notification sent to {chat_id} for {pnr}")

    async def notify_sos_alert(
        self, 
        chat_id: int, 
        message: str,
        location_url: Optional[str] = None
    ):
        """Notify emergency contacts or user about SOS situation."""
        text = f"🚨 <b>ACTIVE SOS ALERT</b> 🚨\n\n{message}"
        if location_url:
            text += f"\n\n📍 <a href='{location_url}'>Track Live Location</a>"
        
        await telegram_dispatcher.send_message(
            chat_id=chat_id,
            text=text,
            inline_keyboard=[[{"text": "📞 Call Authorities", "callback_data": "sos_call"}]]
        )

    async def notify_payment_success(self, chat_id: int, booking_id: str, amount: float):
        """Notify user of successful payment and booking."""
        text = f"✅ <b>Payment Successful!</b>\n\n"
        text += f"Amount: ₹{amount}\n"
        text += f"Booking ID: <code>{booking_id}</code>\n\n"
        text += "Your ticket has been booked. You can download the PDF below."
        
        await telegram_dispatcher.send_message(
            chat_id=chat_id,
            text=text,
            inline_keyboard=keyboard_builder.booking_details(booking_id, "PENDING")
        )

# Global instance
notification_manager = ActiveNotificationManager()
