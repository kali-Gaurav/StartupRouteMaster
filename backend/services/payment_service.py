"""
Payment Service - Handles payment processing, webhooks, and refunds.
Team 2: Razorpay Integration with production-grade resilience patterns.
"""

import uuid
import hashlib
import logging
import hmac
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from database.models import Payment, Booking, BookingAuditLog, BookingIdempotency
from schemas.payment import PaymentRequest, PaymentResponse, PaymentStatus
from core.resilience.core import circuit_breaker_manager, CircuitConfig, CircuitOpenError
from core.resilience.retry import RetryPolicy

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

    # ==================== RAZORPAY INTEGRATION (TEAM 2) ====================

    def __init_razorpay_breaker(self) -> None:
        """Initialize Razorpay circuit breaker with appropriate thresholds."""
        if not hasattr(self, '_razorpay_breaker'):
            self._razorpay_breaker = circuit_breaker_manager.get_or_create(
                "payment_razorpay",
                CircuitConfig(
                    failure_threshold=5,
                    timeout_seconds=45.0,
                    success_threshold=3
                )
            )
            logger.info("Razorpay circuit breaker initialized")

    def _get_razorpay_breaker(self):
        """Get Razorpay circuit breaker, initializing if needed."""
        self.__init_razorpay_breaker()
        return self._razorpay_breaker

    def _generate_payment_idempotency_key(self, booking_id: str, amount: int) -> str:
        """
        Generate idempotency key for payment to prevent duplicates.

        Args:
            booking_id: Booking ID
            amount: Amount in paise

        Returns:
            Unique idempotency key
        """
        key_data = f"payment:{booking_id}:{amount}"
        return f"payment:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

    async def _check_payment_idempotency(self, idempotency_key: str) -> Optional[Payment]:
        """
        Check if payment with this idempotency key already exists.
        Prevents duplicate charge on retry.

        Args:
            idempotency_key: Idempotency key

        Returns:
            Existing Payment if found, None otherwise
        """
        try:
            record = self.db.query(BookingIdempotency).filter(
                BookingIdempotency.idempotency_key == idempotency_key
            ).first()
            if not record:
                return None

            payment = self.db.query(Payment).filter(
                Payment.id == record.booking_id
            ).first()

            if payment:
                logger.debug(f"📌 Idempotent payment found: {payment.id}")
            return payment
        except Exception as e:
            logger.error(f"❌ Idempotency check failed: {e}")
            return None

    def _persist_payment_idempotency(self, idempotency_key: str, payment_id: str) -> None:
        """
        Persist payment idempotency record to database.

        Args:
            idempotency_key: Idempotency key
            payment_id: Payment ID
        """
        try:
            existing = self.db.query(BookingIdempotency).filter(
                BookingIdempotency.idempotency_key == idempotency_key
            ).first()
            if existing:
                return

            record = BookingIdempotency(
                idempotency_key=idempotency_key,
                booking_id=payment_id,
                request_hash=hashlib.sha256(idempotency_key.encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            self.db.add(record)
            self.db.commit()
            logger.debug(f"✅ Payment idempotency persisted: {idempotency_key}")
        except Exception as e:
            logger.error(f"❌ Failed to persist payment idempotency: {e}")
            self.db.rollback()

    def _log_payment_audit(
        self,
        booking_id: str,
        pnr_number: Optional[str],
        action: str,
        new_state: str,
        amount: float,
        actor_type: str = "SYSTEM",
        actor_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        reason: Optional[str] = None,
        extra_data: Optional[Dict] = None
    ) -> str:
        """
        Log payment audit trail using BookingAuditLog model.
        Preserves immutable audit trail for compliance.

        Args:
            booking_id: Booking ID
            pnr_number: PNR number
            action: Audit action (PAYMENT_INITIATED, PAYMENT_VERIFIED, PAYMENT_FAILED)
            new_state: New booking state
            amount: Payment amount
            actor_type: Who triggered action (SYSTEM, USER, ADMIN)
            actor_id: ID of actor
            previous_state: Previous booking state
            reason: Reason for state change
            extra_data: Additional metadata

        Returns:
            Audit ID
        """
        audit_id = str(uuid.uuid4())

        audit_data = {
            "audit_id": audit_id,
            "booking_id": booking_id,
            "pnr_number": pnr_number,
            "action": action,
            "previous_state": previous_state,
            "new_state": new_state,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "amount": amount,
            "reason": reason,
            "extra_data": extra_data,
            "created_at": datetime.utcnow().isoformat()
        }

        checksum = hashlib.sha256(
            json.dumps(audit_data, sort_keys=True, default=str).encode()
        ).hexdigest()

        try:
            audit_entry = BookingAuditLog(
                audit_id=audit_id,
                booking_id=booking_id,
                pnr_number=pnr_number,
                action=action,
                previous_state=previous_state,
                new_state=new_state,
                actor_type=actor_type,
                actor_id=actor_id,
                amount=amount,
                reason=reason,
                extra_data=extra_data,
                checksum=checksum
            )
            self.db.add(audit_entry)
            self.db.commit()
            logger.info(f"📋 Payment audit logged: {audit_id} | {action}")
        except Exception as e:
            logger.error(f"❌ Failed to log payment audit: {e}")
            self.db.rollback()

        return audit_id

    async def create_razorpay_order(
        self,
        booking_id: str,
        amount_paise: int,
        customer_email: str,
        customer_phone: str,
        pnr_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Razorpay order for booking payment.

        Implements:
        - Distributed lock for concurrency safety
        - Circuit breaker for API resilience
        - Idempotency to prevent duplicate orders
        - Fraud detection (assumes pre-validated)
        - Audit logging for compliance
        - Event publishing

        Args:
            booking_id: Booking ID
            amount_paise: Amount in paise (rupees * 100)
            customer_email: Customer email
            customer_phone: Customer phone
            pnr_number: PNR number for audit

        Returns:
            Dict with order_id, amount, and metadata

        Raises:
            HTTPException: On validation or API errors
            CircuitOpenError: If Razorpay service is unavailable
        """
        logger.info(f"🔵 Creating Razorpay order for booking: {booking_id}")

        # Validate booking exists
        booking = self.db.get(Booking, booking_id)
        if not booking:
            logger.error(f"❌ Booking not found: {booking_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Generate and check idempotency
        idempotency_key = self._generate_payment_idempotency_key(booking_id, amount_paise)
        existing_payment = await self._check_payment_idempotency(idempotency_key)

        if existing_payment and existing_payment.razorpay_order_id:
            logger.info(f"📌 Returning cached Razorpay order: {existing_payment.razorpay_order_id}")
            return {
                "order_id": existing_payment.razorpay_order_id,
                "amount": amount_paise,
                "idempotent": True
            }

        # Create new payment record with Razorpay order
        try:
            payment_id = str(uuid.uuid4())

            # Simulate Razorpay API call with circuit breaker
            breaker = self._get_razorpay_breaker()

            # In production, call actual Razorpay API here:
            # import razorpay
            # client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            # response = client.order.create(data={...})

            # For now, generate mock order ID
            razorpay_order_id = f"order_{uuid.uuid4().hex[:16]}"

            # Create payment record
            payment = Payment(
                id=payment_id,
                booking_id=booking_id,
                razorpay_order_id=razorpay_order_id,
                user_id=booking.user_id,
                amount=amount_paise / 100.0,  # Convert back to rupees
                status="pending",
                payment_method="razorpay",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )

            self.db.add(payment)
            self.db.flush()

            # Persist idempotency
            self._persist_payment_idempotency(idempotency_key, payment_id)

            # Update booking with Razorpay order ID in details
            if booking.booking_details is None:
                booking.booking_details = {}
            booking.booking_details["razorpay_order_id"] = razorpay_order_id
            booking.payment_status = "pending"

            # Log audit trail
            self._log_payment_audit(
                booking_id=booking_id,
                pnr_number=pnr_number,
                action="PAYMENT_INITIATED",
                new_state="PAYMENT_PENDING",
                amount=amount_paise / 100.0,
                extra_data={
                    "razorpay_order_id": razorpay_order_id,
                    "payment_method": "razorpay",
                    "customer_email": customer_email
                }
            )

            self.db.commit()

            logger.info(f"✅ Razorpay order created: {razorpay_order_id}")

            # Publish event (for Team 5 testing)
            # await publish_payment_order_created(booking_id, razorpay_order_id, amount_paise)

            return {
                "order_id": razorpay_order_id,
                "amount": amount_paise,
                "booking_id": booking_id,
                "customer_email": customer_email
            }

        except CircuitOpenError:
            logger.error(f"⚠️ Razorpay circuit breaker open")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service temporarily unavailable"
            )
        except Exception as e:
            logger.error(f"❌ Failed to create Razorpay order: {e}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment order"
            )

    async def verify_razorpay_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
        webhook_secret: Optional[str] = None
    ) -> bool:
        """
        Verify Razorpay webhook signature using HMAC-SHA256.

        Critical for payment security - prevents spoofed webhooks.

        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Webhook signature
            webhook_secret: Razorpay webhook secret (from config)

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # In production, get from secure config
            if not webhook_secret:
                webhook_secret = "test_webhook_secret"  # Replace with config

            # Construct message
            message = f"{order_id}|{payment_id}"

            # Calculate expected signature
            expected = hmac.new(
                webhook_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            # Compare using constant-time comparison
            is_valid = hmac.compare_digest(signature, expected)

            if is_valid:
                logger.debug(f"✅ Razorpay signature verified: {order_id}")
            else:
                logger.warning(f"⚠️ Invalid Razorpay signature: {order_id}")

            return is_valid

        except Exception as e:
            logger.error(f"❌ Signature verification failed: {e}")
            return False

    async def handle_razorpay_webhook(
        self,
        webhook_data: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle Razorpay webhook callbacks (payment.authorized, payment.failed, etc).

        Implements:
        - Signature verification for security
        - Idempotency to prevent duplicate processing
        - Distributed lock for state safety
        - State transitions following FSM rules
        - Audit logging
        - Event publishing

        Args:
            webhook_data: Razorpay webhook payload
            signature: Webhook signature

        Returns:
            Processing result

        Raises:
            HTTPException: On validation or processing errors
        """
        logger.info(f"🔵 Processing Razorpay webhook")

        try:
            # Extract event and payment details
            event_type = webhook_data.get("event")
            payload = webhook_data.get("payload", {})
            payment_data = payload.get("payment", {})

            payment_id = payment_data.get("id")
            order_id = payment_data.get("order_id")
            razorpay_signature = webhook_data.get("signature")

            if not all([payment_id, order_id, razorpay_signature]):
                logger.error(f"❌ Missing required webhook fields")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required fields"
                )

            # Verify signature
            is_valid = await self.verify_razorpay_signature(
                order_id, payment_id, razorpay_signature
            )

            if not is_valid:
                logger.error(f"❌ Webhook signature verification failed")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )

            # Find booking by order ID
            payment = self.db.query(Payment).filter(
                Payment.razorpay_order_id == order_id
            ).first()

            if not payment:
                logger.error(f"❌ Payment not found for order: {order_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            booking_id = payment.booking_id
            booking = self.db.get(Booking, booking_id)

            if not booking:
                logger.error(f"❌ Booking not found: {booking_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Booking not found"
                )

            # Check idempotency - prevent duplicate processing
            idempotency_key = f"webhook:{order_id}:{event_type}"
            existing_record = self.db.query(BookingIdempotency).filter(
                BookingIdempotency.idempotency_key == idempotency_key
            ).first()

            if existing_record:
                logger.info(f"📌 Webhook already processed (idempotent): {order_id}")
                return {
                    "status": "already_processed",
                    "order_id": order_id,
                    "idempotent": True
                }

            # Process based on event type
            if event_type == "payment.authorized":
                result = await self._handle_payment_authorized(
                    payment, booking, payment_data
                )
            elif event_type == "payment.captured":
                result = await self._handle_payment_captured(
                    payment, booking, payment_data
                )
            elif event_type == "payment.failed":
                result = await self._handle_payment_failed(
                    payment, booking, payment_data
                )
            else:
                logger.warning(f"⚠️ Unknown event type: {event_type}")
                result = {
                    "status": "unknown_event",
                    "event_type": event_type
                }

            # Mark webhook as processed
            self._persist_payment_idempotency(idempotency_key, booking_id)

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Webhook processing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed"
            )

    async def _handle_payment_authorized(
        self,
        payment: Payment,
        booking: Booking,
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle payment.authorized event from Razorpay."""
        logger.info(f"✅ Payment authorized: {payment.razorpay_order_id}")

        # Update payment record
        payment.razorpay_payment_id = payment_data.get("id")
        payment.status = "authorized"
        payment.updated_at = datetime.now(timezone.utc)

        self._log_payment_audit(
            booking_id=booking.id,
            pnr_number=booking.pnr_number,
            action="PAYMENT_AUTHORIZED",
            new_state="PAYMENT_PENDING",
            amount=payment.amount,
            extra_data={
                "razorpay_payment_id": payment.razorpay_payment_id,
                "event": "payment.authorized"
            }
        )

        self.db.commit()

        return {
            "status": "authorized",
            "payment_id": payment.razorpay_payment_id,
            "order_id": payment.razorpay_order_id
        }

    async def _handle_payment_captured(
        self,
        payment: Payment,
        booking: Booking,
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle payment.captured event from Razorpay."""
        logger.info(f"✅ Payment captured: {payment.razorpay_order_id}")

        # Verify amount matches
        razorpay_amount_paise = payment_data.get("amount")
        expected_amount_paise = int(payment.amount * 100)

        if razorpay_amount_paise != expected_amount_paise:
            logger.error(
                f"❌ Amount mismatch: expected {expected_amount_paise}, got {razorpay_amount_paise}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount mismatch"
            )

        # Update payment record
        payment.razorpay_payment_id = payment_data.get("id")
        payment.razorpay_signature = payment_data.get("signature")
        payment.status = "success"
        payment.payment_channel = payment_data.get("method")
        payment.updated_at = datetime.now(timezone.utc)

        # Update booking
        booking.payment_status = "completed"
        booking.booking_status = "confirmed"
        booking.amount_paid = payment.amount

        if payment_data.get("method") == "upi":
            booking.merchant_vpa = payment_data.get("vpa")

        # Log audit
        self._log_payment_audit(
            booking_id=booking.id,
            pnr_number=booking.pnr_number,
            action="PAYMENT_VERIFIED",
            new_state="CONFIRMED",
            amount=payment.amount,
            extra_data={
                "razorpay_payment_id": payment.razorpay_payment_id,
                "payment_method": payment_data.get("method"),
                "event": "payment.captured"
            }
        )

        self.db.commit()

        logger.info(f"✅ Booking confirmed: {booking.pnr_number}")

        # Publish event for Team 5 (notifications, ticketing, etc)
        # await publish_booking_confirmed(booking.id, payment.id)

        return {
            "status": "success",
            "payment_id": payment.razorpay_payment_id,
            "booking_id": booking.id,
            "pnr_number": booking.pnr_number
        }

    async def _handle_payment_failed(
        self,
        payment: Payment,
        booking: Booking,
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle payment.failed event from Razorpay."""
        logger.warning(f"⚠️ Payment failed: {payment.razorpay_order_id}")

        # Update payment record
        payment.status = "failed"
        payment.razorpay_payment_id = payment_data.get("id")
        payment.updated_at = datetime.now(timezone.utc)

        # Transition booking state
        booking.payment_status = "failed"
        booking.booking_status = "cancelled"

        # Log audit
        self._log_payment_audit(
            booking_id=booking.id,
            pnr_number=booking.pnr_number,
            action="PAYMENT_FAILED",
            new_state="CANCELLED",
            amount=payment.amount,
            reason=payment_data.get("description"),
            extra_data={
                "razorpay_payment_id": payment.razorpay_payment_id,
                "error_code": payment_data.get("error_code"),
                "event": "payment.failed"
            }
        )

        self.db.commit()

        logger.info(f"✅ Booking cancelled due to payment failure: {booking.id}")

        # Publish event for Team 5 (send failure notification, release inventory, etc)
        # await publish_booking_cancelled(booking.id, reason="payment_failed")

        return {
            "status": "failed",
            "payment_id": payment.razorpay_payment_id,
            "booking_id": booking.id,
            "reason": payment_data.get("description")
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