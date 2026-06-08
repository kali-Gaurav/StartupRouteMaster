"""
Payment Service - Handles payment processing, webhooks, and refunds.
"""

import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from database.models import Payment, Booking
from schemas.payment import PaymentRequest, PaymentResponse, PaymentStatus

logger = logging.getLogger("payment_service")


class PaymentProvider(Enum):
    UPI = "upi"
    CARD = "card"
    NET_BANKING = "net_banking"


class PaymentService:
    """Payment processing service."""
    
    def __init__(self, db: Session):
        self.db = db
        self.webhook_secrets = {}  # In production, use secure secret management
    
    async def create_payment(
        self,
        booking_id: str,
        amount: float,
        payment_method: str,
        user_id: str
    ) -> PaymentResponse:
        """
        Create a new payment for a booking.
        
        Args:
            booking_id: ID of the booking
            amount: Payment amount
            payment_method: Payment method (upi, card, net_banking)
            user_id: ID of the user making payment
            
        Returns:
            PaymentResponse with payment details
        """
        # Validate booking exists and is in correct state
        booking = self.db.get(Booking, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        if booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to pay for this booking"
            )
        
        if booking.booking_status not in ["initiated", "payment_pending"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pay for booking in status: {booking.booking_status}"
            )
        
        # Create payment record
        payment_id = str(uuid.uuid4())
        payment = Payment(
            id=payment_id,
            booking_id=booking_id,
            amount=amount,
            payment_method=payment_method,
            status=PaymentStatus.PENDING.value,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        
        self.db.add(payment)
        
        # Generate payment URL based on method
        if payment_method == "upi":
            payment_url = await self._create_upi_payment(payment)
        elif payment_method == "card":
            payment_url = await self._create_card_payment(payment)
        elif payment_method == "net_banking":
            payment_url = await self._create_net_banking_payment(payment)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported payment method: {payment_method}"
            )
        
        payment.payment_url = payment_url
        self.db.commit()
        
        # Update booking status
        booking.booking_status = "payment_pending"
        booking.payment_id = payment_id
        self.db.commit()
        
        return PaymentResponse(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=amount,
            status=PaymentStatus.PENDING,
            payment_url=payment_url,
            expires_at=payment.expires_at
        )
    
    async def _create_upi_payment(self, payment: Payment) -> str:
        """Create UPI payment URL."""
        # In production, integrate with UPI gateway (PhonePe, Paytm, etc.)
        upi_id = "booking@upi"  # Configure in settings
        return f"upi://pay?pa={upi_id}&pn=TravelBooking&am={payment.amount}&tn=Booking {payment.booking_id}&tr={payment.id}"
    
    async def _create_card_payment(self, payment: Payment) -> str:
        """Create card payment URL."""
        # In production, integrate with payment gateway (Razorpay, Stripe, etc.)
        return f"/payment/card/{payment.id}?amount={payment.amount}"
    
    async def _create_net_banking_payment(self, payment: Payment) -> str:
        """Create net banking payment URL."""
        return f"/payment/nb/{payment.id}?amount={payment.amount}"
    
    # ==================== MOCK PAYMENT METHODS FOR DEMO ====================
    
    async def create_mock_payment(
        self,
        booking_id: str,
        amount: float,
        user_id: str
    ) -> PaymentResponse:
        """
        Create a mock payment for demo purposes.
        
        This simulates the payment flow without actual payment processing.
        """
        payment_id = f"mock_{uuid.uuid4().hex[:12]}"
        
        # Create payment record
        payment = Payment(
            id=payment_id,
            booking_id=booking_id,
            amount=amount,
            payment_method="upi",
            status=PaymentStatus.PENDING.value,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        
        self.db.add(payment)
        self.db.commit()
        
        # Generate mock UPI QR code
        upi_id = "routemaster@upi"
        qr_data = f"upi://pay?pa={upi_id}&pn=RouteMaster&am={amount}&tn=Booking_{booking_id}"
        
        return PaymentResponse(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=amount,
            status=PaymentStatus.PENDING,
            payment_url=f"/payment/mock/{payment_id}",
            qr_code=qr_data,
            upi_id=upi_id,
            expires_at=payment.expires_at
        )
    
    async def confirm_mock_payment(
        self,
        payment_id: str,
        transaction_details: Dict[str, Any] = None
    ) -> PaymentResponse:
        """
        Confirm a mock payment.
        """
        payment = self.db.execute(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        ).scalar_one_or_none()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment.status == PaymentStatus.SUCCESS.value:
            # Already confirmed - return existing
            return PaymentResponse(
                payment_id=payment.id,
                booking_id=payment.booking_id,
                amount=payment.amount,
                status=PaymentStatus.SUCCESS,
                payment_url=payment.payment_url or "",
                transaction_id=payment.transaction_id
            )
        
        # Update payment
        payment.status = PaymentStatus.SUCCESS.value
        payment.transaction_id = transaction_details.get("transaction_id", f"txn_{uuid.uuid4().hex[:8]}") if transaction_details else f"txn_{uuid.uuid4().hex[:8]}"
        payment.completed_at = datetime.now(timezone.utc)
        
        # Update booking status
        booking = self.db.execute(
            select(Booking).where(Booking.id == payment.booking_id).with_for_update()
        ).scalar_one_or_none()
        if booking:
            booking.booking_status = "confirmed"
            booking.amount_paid = payment.amount
            booking.payment_completed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return PaymentResponse(
            payment_id=payment.id,
            booking_id=payment.booking_id,
            amount=payment.amount,
            status=PaymentStatus.SUCCESS,
            payment_url=payment.payment_url or "",
            transaction_id=payment.transaction_id
        )
    
    async def handle_webhook(
        self,
        provider: str,
        payload: Dict[str, Any],
        signature: str
    ) -> Dict[str, Any]:
        """
        Handle payment gateway webhook callback.
        
        Args:
            provider: Payment provider name
            payload: Webhook payload
            signature: Webhook signature for verification
            
        Returns:
            Result of webhook processing
        """
        # Verify webhook signature
        if not self._verify_webhook_signature(provider, payload, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Extract payment details from payload
        payment_id = payload.get("payment_id") or payload.get("transaction_id")
        status_str = payload.get("status")
        upi_tx_id = payload.get("upi_tx_id")
        utr_number = payload.get("utr_number")
        
        if not payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment ID not found in webhook"
            )
        
        # Get payment record
        payment = self.db.execute(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        ).scalar_one_or_none()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Check for idempotent update
        if payment.status == status_str:
            return {"status": "already_processed", "payment_id": payment_id}
        
        # Map provider status to our status
        new_status = self._map_provider_status(provider, status_str)
        
        # Update payment
        payment.status = new_status.value
        payment.completed_at = datetime.now(timezone.utc)
        if upi_tx_id:
            payment.upi_tx_id = upi_tx_id
        if utr_number:
            payment.utr_number = utr_number
        payment.webhook_payload = str(payload)
        
        # Handle booking update
        booking = self.db.execute(
            select(Booking).where(Booking.id == payment.booking_id).with_for_update()
        ).scalar_one_or_none()
        if booking:
            if new_status == PaymentStatus.SUCCESS:
                await self._handle_successful_payment(booking, payment)
            elif new_status in [PaymentStatus.FAILED, PaymentStatus.CANCELLED]:
                await self._handle_failed_payment(booking, payment)
        
        self.db.commit()
        
        return {
            "status": "processed",
            "payment_id": payment_id,
            "new_status": new_status.value
        }
    
    def _verify_webhook_signature(
        self,
        provider: str,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature from payment provider."""
        # In production, implement provider-specific signature verification
        secret = self.webhook_secrets.get(provider, "")
        if not secret:
            # For development, accept all signatures
            return True
        
        # Example: HMAC verification
        import hmac
        expected = hmac.new(
            secret.encode(),
            str(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def _map_provider_status(
        self,
        provider: str,
        provider_status: str
    ) -> PaymentStatus:
        """Map provider-specific status to our status enum."""
        status_mapping = {
            "success": PaymentStatus.SUCCESS,
            "completed": PaymentStatus.SUCCESS,
            "captured": PaymentStatus.SUCCESS,
            "failed": PaymentStatus.FAILED,
            "declined": PaymentStatus.FAILED,
            "cancelled": PaymentStatus.CANCELLED,
            "pending": PaymentStatus.PENDING,
            "processing": PaymentStatus.PROCESSING,
        }
        
        normalized = provider_status.lower()
        return status_mapping.get(normalized, PaymentStatus.UNKNOWN)
    
    async def _handle_successful_payment(
        self,
        booking: Booking,
        payment: Payment
    ) -> None:
        """Handle successful payment confirmation."""
        booking.booking_status = "confirmed"
        booking.amount_paid = payment.amount
        booking.payment_completed_at = datetime.now(timezone.utc)
        booking.upi_tx_id = payment.upi_tx_id
        booking.utr_number = payment.utr_number
        
        # Confirm seat allocation
        from services.inventory_service import get_inventory_service
        inv_service = get_inventory_service(self.db)
        await inv_service.confirm_seats(booking.id)
        
        logger.info(f"Booking {booking.pnr_number} confirmed with payment {payment.id}")
    
    async def _handle_failed_payment(
        self,
        booking: Booking,
        payment: Payment
    ) -> None:
        """Handle failed payment."""
        booking.booking_status = "payment_failed"
        booking.payment_failure_reason = payment.webhook_payload
        
        # Release seat lock
        from services.inventory_service import get_inventory_service
        inv_service = get_inventory_service(self.db)
        await inv_service.release_seats(booking.id)
        
        logger.info(f"Payment failed for booking {booking.pnr_number}: {payment.webhook_payload}")
    
    async def process_refund(
        self,
        payment_id: str,
        amount: Optional[float] = None,
        reason: str = "customer_request"
    ) -> PaymentResponse:
        """
        Process refund for a payment.
        
        Args:
            payment_id: Original payment ID
            amount: Refund amount (full if not specified)
            reason: Refund reason
            
        Returns:
            Refund payment response
        """
        original_payment = self.db.execute(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        ).scalar_one_or_none()
        if not original_payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original payment not found"
            )
        
        if original_payment.status != PaymentStatus.SUCCESS.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only refund successful payments"
            )
        
        refund_amount = amount or original_payment.amount
        
        # Create refund record
        refund_id = str(uuid.uuid4())
        refund = Payment(
            id=refund_id,
            booking_id=original_payment.booking_id,
            amount=-refund_amount,  # Negative for refund
            payment_method=original_payment.payment_method,
            status=PaymentStatus.REFUNDED.value,
            created_at=datetime.now(timezone.utc),
            refund_reason=reason,
            original_payment_id=payment_id
        )
        
        self.db.add(refund)
        
        # Update original payment
        original_payment.refund_id = refund_id
        original_payment.refund_amount = refund_amount
        
        # Update booking
        booking = self.db.execute(
            select(Booking).where(Booking.id == original_payment.booking_id).with_for_update()
        ).scalar_one_or_none()
        if booking:
            booking.booking_status = "refunded"
            booking.refund_amount = refund_amount
            booking.refund_processed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        return PaymentResponse(
            payment_id=refund_id,
            booking_id=original_payment.booking_id,
            amount=refund_amount,
            status=PaymentStatus.REFUNDED,
            metadata={"original_payment_id": payment_id, "reason": reason}
        )
    
    async def get_payment(self, payment_id: str) -> Payment:
        """Get payment details."""
        payment = self.db.get(Payment, payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        return payment
    
    async def get_payments_for_booking(
        self,
        booking_id: str
    ) -> list[Payment]:
        """Get all payments for a booking."""
        result = self.db.execute(
            select(Payment).where(Payment.booking_id == booking_id)
        ).scalars().all()
        return list(result)
    
    async def reconcile_payments(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate reconciliation report for payments.
        
        Args:
            start_date: Start of reconciliation period
            end_date: End of reconciliation period
            
        Returns:
            Reconciliation report
        """
        result = self.db.execute(
            select(Payment).where(
                and_(
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date
                )
            )
        ).scalars().all()
        
        payments = list(result)
        
        total_collected = sum(p.amount for p in payments if p.status == PaymentStatus.SUCCESS.value)
        total_refunded = sum(abs(p.amount) for p in payments if p.status == PaymentStatus.REFUNDED.value)
        total_pending = sum(p.amount for p in payments if p.status == PaymentStatus.PENDING.value)
        total_failed = sum(p.amount for p in payments if p.status == PaymentStatus.FAILED.value)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_transactions": len(payments),
                "total_collected": total_collected,
                "total_refunded": total_refunded,
                "net_revenue": total_collected - total_refunded,
                "pending_amount": total_pending,
                "failed_amount": total_failed
            },
            "by_status": {
                "success": len([p for p in payments if p.status == PaymentStatus.SUCCESS.value]),
                "pending": len([p for p in payments if p.status == PaymentStatus.PENDING.value]),
                "failed": len([p for p in payments if p.status == PaymentStatus.FAILED.value]),
                "refunded": len([p for p in payments if p.status == PaymentStatus.REFUNDED.value])
            },
            "by_method": {
                "upi": sum(p.amount for p in payments if p.payment_method == "upi" and p.status == PaymentStatus.SUCCESS.value),
                "card": sum(p.amount for p in payments if p.payment_method == "card" and p.status == PaymentStatus.SUCCESS.value),
                "net_banking": sum(p.amount for p in payments if p.payment_method == "net_banking" and p.status == PaymentStatus.SUCCESS.value)
            }
        }


# Singleton instance
payment_service = None

def get_payment_service(db: Session) -> PaymentService:
    """Get or create payment service instance."""
    global payment_service
    if payment_service is None:
        payment_service = PaymentService(db)
    return payment_service


# ==================== Mock Payment Methods for Demo ====================

class MockPaymentService:
    """
    Mock payment service for demo and testing purposes.
    Simulates payment flow without actual payment gateway integration.
    """
    
    def __init__(self):
        self.mock_payments: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("mock_payment_service")
    
    async def create_mock_payment(
        self,
        booking_id: str,
        amount: float,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create a mock payment for demo purposes.
        
        Args:
            booking_id: ID of the booking
            amount: Payment amount
            user_id: ID of the user
            
        Returns:
            Dict with payment details including mock payment URL
        """
        import asyncio
        import random
        
        payment_id = str(uuid.uuid4())
        
        # Create mock payment record
        mock_payment = {
            "payment_id": payment_id,
            "booking_id": booking_id,
            "amount": amount,
            "user_id": user_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            "mock_payment_url": f"/mock_payment/{payment_id}?amount={amount}",
            "mock_verification_code": f"MOCK-{random.randint(1000, 9999)}"
        }
        
        self.mock_payments[payment_id] = mock_payment
        self.logger.info(f"Created mock payment {payment_id} for booking {booking_id}")
        
        return mock_payment
    
    async def verify_mock_payment(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """
        Verify a mock payment (simulates payment gateway verification).
        
        Args:
            payment_id: ID of the payment to verify
            
        Returns:
            Dict with verification result
        """
        import random
        import asyncio
        
        if payment_id not in self.mock_payments:
            return {
                "success": False,
                "error": "Payment not found",
                "payment_id": payment_id
            }
        
        payment = self.mock_payments[payment_id]
        
        # Simulate payment processing delay
        await asyncio.sleep(0.5)
        
        # Simulate 95% success rate
        if random.random() < 0.95:
            payment["status"] = "success"
            payment["verified_at"] = datetime.now(timezone.utc).isoformat()
            payment["upi_tx_id"] = f"UPI{random.randint(10000000, 99999999)}"
            payment["utr_number"] = f"{random.randint(100000000000, 999999999999)}"
            
            self.logger.info(f"Mock payment {payment_id} verified successfully")
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": "success",
                "upi_tx_id": payment["upi_tx_id"],
                "utr_number": payment["utr_number"],
                "message": "Payment verified successfully"
            }
        else:
            payment["status"] = "failed"
            payment["failed_at"] = datetime.now(timezone.utc).isoformat()
            payment["failure_reason"] = "Mock payment failure for testing"
            
            self.logger.warning(f"Mock payment {payment_id} failed (simulated)")
            
            return {
                "success": False,
                "payment_id": payment_id,
                "status": "failed",
                "error": "Payment verification failed",
                "failure_reason": "Mock payment failure for testing"
            }
    
    async def simulate_payment_flow(
        self,
        booking_id: str,
        amount: float,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Simulate complete payment flow with success message after delay.
        
        Args:
            booking_id: ID of the booking
            amount: Payment amount
            user_id: ID of the user
            
        Returns:
            Dict with complete payment flow result
        """
        import asyncio
        
        # Step 1: Create payment
        payment = await self.create_mock_payment(booking_id, amount, user_id)
        
        # Step 2: Simulate payment page delay
        await asyncio.sleep(2)
        
        # Step 3: Verify payment
        result = await self.verify_mock_payment(payment["payment_id"])
        
        return {
            "payment_id": payment["payment_id"],
            "booking_id": booking_id,
            "amount": amount,
            "status": result["status"],
            "verification_result": result,
            "message": "Payment completed successfully!" if result["success"] else "Payment failed. Please try again."
        }
    
    def get_mock_payment_status(
        self,
        payment_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a mock payment.
        
        Args:
            payment_id: ID of the payment
            
        Returns:
            Payment dict or None if not found
        """
        return self.mock_payments.get(payment_id)
    
    def clear_mock_payments(self) -> None:
        """Clear all mock payment records (for testing)."""
        self.mock_payments.clear()
        self.logger.info("Cleared all mock payments")


# Singleton instance for mock payment service
mock_payment_service = MockPaymentService()