"""
Email Provider Integration - Mailgun
Handles sending emails via Mailgun API
"""

import os
import logging
import httpx
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger("email_provider")


@dataclass
class EmailResult:
    """Result of email send attempt."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class MailgunProvider:
    """Mailgun email provider implementation."""

    def __init__(self):
        self.api_key = os.getenv("MAILGUN_API_KEY", "")
        self.domain = os.getenv("MAILGUN_DOMAIN", "")
        self.from_email = os.getenv("MAILGUN_FROM_EMAIL", "noreply@routemaster.app")
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"

        if not self.api_key or not self.domain:
            logger.warning("Mailgun credentials not configured - emails will be logged only")

    async def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: Optional[str] = None,
        reply_to: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> EmailResult:
        """
        Send email via Mailgun.

        Args:
            to: Recipient email address
            subject: Email subject
            text: Plain text body
            html: HTML body (optional)
            reply_to: Reply-to address (optional)
            tags: Tags for email tracking (optional)

        Returns:
            EmailResult with success status and message ID
        """

        # Fallback to logging if not configured
        if not self.api_key or not self.domain:
            logger.info(f"[EMAIL STUB] To: {to}")
            logger.info(f"[EMAIL STUB] Subject: {subject}")
            logger.info(f"[EMAIL STUB] Body: {text[:100]}...")
            return EmailResult(
                success=True,
                message_id=f"stub_{hash(to + subject)}"
            )

        try:
            data = {
                "from": self.from_email,
                "to": to,
                "subject": subject,
                "text": text
            }

            if html:
                data["html"] = html

            if reply_to:
                data["h:Reply-To"] = reply_to

            if tags:
                for tag in tags:
                    data[f"o:tag"] = tag

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    auth=("api", self.api_key),
                    data=data,
                    timeout=10.0
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    message_id = result.get("id")
                    logger.info(f"Email sent to {to}: {message_id}")
                    return EmailResult(success=True, message_id=message_id)
                else:
                    error = response.json().get("message", response.text)
                    logger.error(f"Mailgun error: {error}")
                    return EmailResult(success=False, error=error)

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return EmailResult(success=False, error=str(e))


class EmailTemplates:
    """Email template builder."""

    @staticmethod
    def booking_confirmed(pnr: str, train: str, from_station: str, to_station: str, date: str, passenger_name: str) -> tuple:
        """Generate booking confirmation email."""
        subject = f"Booking Confirmed - PNR {pnr}"
        text = f"""
Hello {passenger_name},

Your booking has been confirmed!

PNR: {pnr}
Train: {train}
Route: {from_station} → {to_station}
Date: {date}

Have a safe journey with RouteMaster!

---
RouteMaster Train Booking
"""

        html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Booking Confirmed! 🎫</h2>

        <p>Hello {passenger_name},</p>

        <p>Your booking has been confirmed. Here are your details:</p>

        <div style="background-color: #f3f4f6; padding: 15px; border-left: 4px solid #2563eb; margin: 20px 0;">
            <p><strong>PNR:</strong> {pnr}</p>
            <p><strong>Train:</strong> {train}</p>
            <p><strong>Route:</strong> {from_station} → {to_station}</p>
            <p><strong>Date:</strong> {date}</p>
        </div>

        <p>Have a safe journey with RouteMaster!</p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="color: #666; font-size: 12px;">RouteMaster Train Booking Service</p>
    </div>
</body>
</html>
"""
        return subject, text, html

    @staticmethod
    def payment_received(amount: float, pnr: str) -> tuple:
        """Generate payment confirmation email."""
        subject = f"Payment Received - ₹{amount}"
        text = f"""
Hello,

Your payment of ₹{amount} has been received and confirmed.

PNR: {pnr}
Status: Payment Confirmed

Your booking is now active. Show your booking confirmation at the station.

---
RouteMaster Train Booking
"""

        html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #16a34a;">Payment Received ✓</h2>

        <p>Your payment has been confirmed!</p>

        <div style="background-color: #f0fdf4; padding: 15px; border-left: 4px solid #16a34a; margin: 20px 0;">
            <p style="font-size: 24px; color: #16a34a;"><strong>₹{amount}</strong></p>
            <p><strong>PNR:</strong> {pnr}</p>
            <p><strong>Status:</strong> Payment Confirmed</p>
        </div>

        <p>Your booking is now active. Please keep your booking confirmation handy and show it at the station.</p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="color: #666; font-size: 12px;">RouteMaster Train Booking Service</p>
    </div>
</body>
</html>
"""
        return subject, text, html


# Singleton instance
_email_provider = None

def get_email_provider() -> MailgunProvider:
    """Get or create email provider instance."""
    global _email_provider
    if _email_provider is None:
        _email_provider = MailgunProvider()
    return _email_provider
