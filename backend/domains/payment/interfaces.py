"""Payment Domain Interfaces

Abstract protocols for payment processing.
All implementations must follow these interfaces.
"""

from typing import Protocol, Optional
from dataclasses import dataclass
from enum import Enum


class PaymentStatus(Enum):
    """Payment transaction states."""
    PENDING = "PENDING"           # Awaiting processing
    SUCCESS = "SUCCESS"           # Payment successful
    FAILED = "FAILED"            # Payment failed
    REFUNDED = "REFUNDED"        # Refunded after payment


@dataclass
class PaymentResult:
    """Result of a payment transaction."""
    payment_id: str
    booking_id: str
    amount: float
    status: PaymentStatus
    transaction_id: Optional[str]  # External gateway transaction ID
    error_message: Optional[str]   # Error if failed
    created_at: float  # timestamp


class PaymentProcessor(Protocol):
    """
    Abstract contract for payment processing.

    All payment implementations in domains/payment/
    must follow this interface.
    """

    async def process_payment(
        self,
        booking_id: str,
        amount: float,
        payment_method: str,  # "CREDIT_CARD", "DEBIT_CARD", "UPI", "PAYPAL", etc
        payment_token: str,   # Token/nonce from frontend
    ) -> PaymentResult:
        """
        Process payment for a booking.

        Args:
            booking_id: Associated booking ID
            amount: Amount to charge
            payment_method: Method (CREDIT_CARD, UPI, etc)
            payment_token: Token from payment frontend

        Returns:
            PaymentResult with status

        Raises:
            PaymentGatewayError: Gateway down/timeout
            InvalidPaymentError: Invalid method/token
        """
        ...

    async def refund_payment(
        self,
        payment_id: str,
        reason: Optional[str] = None,
    ) -> PaymentResult:
        """
        Refund a successful payment.

        Args:
            payment_id: Payment to refund
            reason: Refund reason

        Returns:
            Updated PaymentResult with REFUNDED status
        """
        ...

    async def get_payment(self, payment_id: str) -> Optional[PaymentResult]:
        """Get payment details."""
        ...

    async def verify_payment(
        self,
        payment_id: str,
        external_transaction_id: str,
    ) -> bool:
        """
        Verify payment with external gateway.

        Used for webhooks/confirmations from gateway.
        """
        ...
