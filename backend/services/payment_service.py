import httpx
import hashlib
import hmac
import logging
from typing import Dict, Optional, Tuple

from backend.config import Config

logger = logging.getLogger(__name__)

RAZORPAY_API_URL = "https://api.razorpay.com/v1"


class PaymentService:
    """Handle Razorpay payment operations using an asynchronous HTTP client."""

    def __init__(self):
        self.key_id = Config.RAZORPAY_KEY_ID
        self.key_secret = Config.RAZORPAY_KEY_SECRET

        if not self.key_id or self.key_id == "your_razorpay_key_id":
            logger.warning("Razorpay key_id not configured")
        if not self.key_secret or self.key_secret == "your_razorpay_key_secret":
            logger.warning("Razorpay key_secret not configured")

    def is_configured(self) -> bool:
        """Check if Razorpay is properly configured."""
        return bool(
            self.key_id
            and self.key_id != "your_razorpay_key_id"
            and self.key_secret
            and self.key_secret != "your_razorpay_key_secret"
        )

    async def create_order(
        self,
        amount_rupees: float = 39,
        receipt_id: str = "route_unlock",
        customer_email: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """Create Razorpay order asynchronously."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "Razorpay not configured. Please contact admin.",
            }

        try:
            amount_paise = int(amount_rupees * 100)
            payload = {
                "amount": amount_paise, "currency": "INR", "receipt": receipt_id,
                "notes": {
                    "customer_email": customer_email,
                    "description": description,
                }
            }
            headers = {"X-Razorpay-IDEMPOTENCY": idempotency_key} if idempotency_key else {}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{RAZORPAY_API_URL}/orders",
                    json=payload,
                    auth=(self.key_id, self.key_secret),
                    headers=headers,
                    timeout=10,
                )

            if response.status_code == 200:
                order_data = response.json()
                logger.info(f"Order created: {order_data['id']}")
                return {
                    "success": True, "order_id": order_data["id"], "amount": amount_rupees,
                    "currency": "INR", "key_id": self.key_id,
                }
            else:
                logger.error(f"Order creation failed: {response.text}")
                return {"success": False, "error": "Failed to create payment order"}
        except httpx.RequestError as e:
            logger.error(f"Payment API error: {e}")
            return {"success": False, "error": "Payment service unavailable"}

    def verify_payment(
        self,
        razorpay_payment_id: str,
        razorpay_order_id: str,
        razorpay_signature: str,
    ) -> Tuple[bool, Optional[str]]:
        """Verify Razorpay payment signature."""
        if not self.is_configured():
            return False, "Razorpay not configured"
        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                self.key_secret.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            if hmac.compare_digest(generated_signature, razorpay_signature):
                logger.info(f"Payment verified: {razorpay_payment_id}")
                return True, None
            else:
                logger.warning(f"Signature mismatch for payment: {razorpay_payment_id}")
                return False, "Signature verification failed"
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
                self.key_secret.encode(), body, hashlib.sha256
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

    async def fetch_payment_details(self, payment_id: str) -> Optional[Dict]:
        """Fetch payment details from Razorpay asynchronously."""
        if not self.is_configured(): return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{RAZORPAY_API_URL}/payments/{payment_id}",
                    auth=(self.key_id, self.key_secret),
                    timeout=5,
                )
            return response.json() if response.status_code == 200 else None
        except httpx.RequestError as e:
            logger.error(f"Payment fetch error: {e}")
            return None

    async def refund_payment(
        self, payment_id: str, amount_rupees: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """Create refund for a payment asynchronously."""
        if not self.is_configured(): return False, "Razorpay not configured"
        try:
            payload = {"amount": int(amount_rupees * 100)} if amount_rupees else {}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{RAZORPAY_API_URL}/payments/{payment_id}/refund",
                    json=payload,
                    auth=(self.key_id, self.key_secret),
                    timeout=10,
                )
            if response.status_code in [200, 201]:
                logger.info(f"Refund created: {response.json().get('id')}")
                return True, None
            else:
                logger.error(f"Refund failed: {response.text}")
                return False, "Refund failed"
        except httpx.RequestError as e:
            logger.error(f"Refund error: {e}")
            return False, str(e)

    async def fetch_payments_for_order(self, order_id: str) -> Optional[Dict]:
        """Fetch all payments for a given Razorpay order asynchronously."""
        if not self.is_configured(): return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{RAZORPAY_API_URL}/orders/{order_id}/payments",
                    auth=(self.key_id, self.key_secret),
                    timeout=5,
                )
            return response.json() if response.status_code == 200 else None
        except httpx.RequestError as e:
            logger.error(f"Payment fetch error for order {order_id}: {e}")
            return None

    async def fetch_order_details(self, order_id: str) -> Optional[Dict]:
        """Fetch order details from Razorpay asynchronously."""
        if not self.is_configured(): return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{RAZORPAY_API_URL}/orders/{order_id}",
                    auth=(self.key_id, self.key_secret),
                    timeout=5,
                )
            return response.json() if response.status_code == 200 else None
        except httpx.RequestError as e:
            logger.error(f"Order fetch error for {order_id}: {e}")
            return None

