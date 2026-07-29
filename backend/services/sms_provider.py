"""
SMS Provider Integration - Twilio
Handles sending SMS via Twilio API
"""

import os
import logging
import httpx
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlencode

logger = logging.getLogger("sms_provider")


@dataclass
class SMSResult:
    """Result of SMS send attempt."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class TwilioProvider:
    """Twilio SMS provider implementation."""

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"

        if not self.account_sid or not self.auth_token or not self.from_number:
            logger.warning("Twilio credentials not configured - SMS will be logged only")

    async def send(
        self,
        to: str,
        message: str
    ) -> SMSResult:
        """
        Send SMS via Twilio.

        Args:
            to: Recipient phone number (E.164 format: +919876543210)
            message: SMS message text (max 160 characters)

        Returns:
            SMSResult with success status and message ID
        """

        # Fallback to logging if not configured
        if not self.account_sid or not self.auth_token or not self.from_number:
            logger.info(f"[SMS STUB] To: {to}")
            logger.info(f"[SMS STUB] Message: {message}")
            return SMSResult(
                success=True,
                message_id=f"stub_{hash(to + message)}"
            )

        try:
            # Validate phone number format
            if not to.startswith("+"):
                to = f"+{to}"

            # Truncate message if too long
            if len(message) > 160:
                logger.warning(f"SMS message too long ({len(message)} chars), truncating")
                message = message[:157] + "..."

            data = {
                "From": self.from_number,
                "To": to,
                "Body": message
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/Messages.json",
                    auth=(self.account_sid, self.auth_token),
                    data=data,
                    timeout=10.0
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    message_id = result.get("sid")
                    logger.info(f"SMS sent to {to}: {message_id}")
                    return SMSResult(success=True, message_id=message_id)
                else:
                    error = response.json().get("message", response.text)
                    logger.error(f"Twilio error: {error}")
                    return SMSResult(success=False, error=error)

        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return SMSResult(success=False, error=str(e))


class SMSTemplates:
    """SMS template builder."""

    @staticmethod
    def booking_confirmed(pnr: str, train: str, date: str) -> str:
        """Generate booking confirmation SMS."""
        return f"RouteMaster: Your booking confirmed! PNR: {pnr}, Train: {train}, Date: {date}. Have a safe journey!"

    @staticmethod
    def payment_received(amount: float, pnr: str) -> str:
        """Generate payment confirmation SMS."""
        return f"RouteMaster: Payment of ₹{amount} received for PNR {pnr}. Your booking is confirmed!"

    @staticmethod
    def pnr_status(pnr: str, status: str) -> str:
        """Generate PNR status update SMS."""
        return f"RouteMaster: PNR {pnr} status - {status}"

    @staticmethod
    def delay_alert(train: str, delay_minutes: int, arrival_time: str) -> str:
        """Generate delay alert SMS."""
        return f"Alert: {train} delayed by {delay_minutes}m. New arrival: {arrival_time}"


# Singleton instance
_sms_provider = None

def get_sms_provider() -> TwilioProvider:
    """Get or create SMS provider instance."""
    global _sms_provider
    if _sms_provider is None:
        _sms_provider = TwilioProvider()
    return _sms_provider
