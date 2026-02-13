import requests
import hashlib
import hmac
import logging
from typing import Dict, Optional, Tuple
from uuid import UUID

from config import Config

logger = logging.getLogger(__name__)

RAZORPAY_API_URL = "https://api.razorpay.com/v1"


class PaymentService:
    """Handle Razorpay payment operations."""

    def __init__(self):
        self.key_id = Config.RAZORPAY_KEY_ID
        self.key_secret = Config.RAZORPAY_KEY_SECRET

        if not self.key_id or self.key_id == "your_razorpay_key_id":
            logger.warning("Razorpay key_id not configured")
        if not self.key_secret or self.key_secret == "your_razorpay_key_secret":
            logger.warning("Razorpay key_secret not configured")

    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured."""
        # Ensure a strict boolean is returned (not the last truthy string)
        return bool(
            self.key_id
            and self.key_id != "your_razorpay_key_id"
            and self.key_secret
            and self.key_secret != "your_razorpay_key_secret"
        )

    def create_order(
        self,
        amount_rupees: float = 39,
        receipt_id: str = "route_unlock",
        customer_email: Optional[str] = None,
    ) -> Dict:
        """
        Create Razorpay order for route unlock.

        Returns order details with order_id if successful.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Razorpay not configured. Please contact admin.",
            }

        try:
            amount_paise = int(amount_rupees * 100)

            payload = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt_id,
            }

            if customer_email:
                payload["customer_notify"] = 1
                payload["notes"] = {"customer_email": customer_email}

            response = requests.post(
                f"{RAZORPAY_API_URL}/orders",
                json=payload,
                auth=(self.key_id, self.key_secret),
                timeout=5,
            )

            if response.status_code == 200:
                order_data = response.json()
                logger.info(f"Order created: {order_data['id']}")
                return {
                    "success": True,
                    "order_id": order_data["id"],
                    "amount": amount_rupees,
                    "currency": "INR",
                    "key_id": self.key_id,
                }
            else:
                logger.error(f"Order creation failed: {response.text}")
                return {
                    "success": False,
                    "error": "Failed to create payment order",
                }
        except requests.RequestException as e:
            logger.error(f"Payment API error: {e}")
            return {
                "success": False,
                "error": "Payment service unavailable",
            }

    def verify_payment(
        self,
        razorpay_payment_id: str,
        razorpay_order_id: str,
        razorpay_signature: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify Razorpay payment signature.

        Returns (is_valid, error_message)
        """
        if not self.is_configured():
            return False, "Razorpay not configured"

        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).hexdigest()

            is_valid = generated_signature == razorpay_signature
            error_msg = None if is_valid else "Signature verification failed"

            if is_valid:
                logger.info(f"Payment verified: {razorpay_payment_id}")
            else:
                logger.warning(f"Signature mismatch for payment: {razorpay_payment_id}")

            return is_valid, error_msg

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False, str(e)

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verifies the signature of a webhook request."""
        if not self.is_configured():
            logger.error("Cannot verify webhook signature, Razorpay keys not configured.")
            return False
        
        try:
            generated_signature = hmac.new(
                self.key_secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
            
            if hmac.compare_digest(generated_signature, signature):
                logger.info("Webhook signature verified successfully.")
                return True
            else:
                logger.warning("Webhook signature mismatch.")
                return False
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    def fetch_payment_details(self, payment_id: str) -> Optional[Dict]:
        """Fetch payment details from Razorpay."""
        if not self.is_configured():
            return None

        try:
            response = requests.get(
                f"{RAZORPAY_API_URL}/payments/{payment_id}",
                auth=(self.key_id, self.key_secret),
                timeout=5,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch payment: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Payment fetch error: {e}")
            return None

    def refund_payment(
        self,
        payment_id: str,
        amount_rupees: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Create refund for a payment.

        Returns (success, error_message)
        """
        if not self.is_configured():
            return False, "Razorpay not configured"

        try:
            payload = {}
            if amount_rupees:
                payload["amount"] = int(amount_rupees * 100)

            response = requests.post(
                f"{RAZORPAY_API_URL}/payments/{payment_id}/refund",
                json=payload,
                auth=(self.key_id, self.key_secret),
                timeout=5,
            )

            if response.status_code in [200, 201]:
                refund_data = response.json()
                logger.info(f"Refund created: {refund_data.get('id')}")
                return True, None
            else:
                logger.error(f"Refund failed: {response.text}")
                return False, "Refund failed"

        except requests.RequestException as e:
            logger.error(f"Refund error: {e}")
            return False, str(e)
