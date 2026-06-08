"""
Payment Webhook Routes - Handle payment provider callbacks.

This module provides webhook endpoints for receiving payment status updates
from various payment providers. It handles signature verification, idempotency
checking, and orchestrates booking confirmation/cancellation based on payment status.
"""

import logging
import hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Header, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import Payment, Booking
from schemas.payment import PaymentStatus as DBPaymentStatus

logger = logging.getLogger("api")

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# =============================================================================
# Pydantic Models for Webhook Payloads
# =============================================================================

class WebhookPayload(BaseModel):
    """Validated webhook payload from payment providers."""
    payment_id: str = Field(..., description="Internal payment ID")
    status: str = Field(..., description="Payment status from provider")
    amount: float = Field(..., ge=0, description="Payment amount")
    transaction_id: Optional[str] = Field(None, description="Provider transaction ID")
    utr_number: Optional[str] = Field(None, description="UTR number for UPI payments")
    provider_reference: Optional[str] = Field(None, description="Provider's payment reference")
    currency: str = Field("INR", description="Currency code")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        extra = "allow"  # Allow additional fields from providers


class WebhookResponse(BaseModel):
    """Standard webhook response."""
    status: str = Field(..., description="Processing status")
    payment_id: str = Field(..., description="Payment ID")
    booking_id: Optional[str] = Field(None, description="Associated booking ID")
    message: str = Field(..., description="Human-readable message")


class ErrorResponse(BaseModel):
    """Error response for webhooks."""
    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error details")
    code: int = Field(..., description="HTTP status code")


# =============================================================================
# Signature Verification
# =============================================================================

def _verify_signature(provider: str, payload: dict, signature: str, secret: str = "") -> bool:
    """
    Verify webhook signature from payment provider.
    
    Different providers use different signature algorithms:
    - Razorpay: HMAC-SHA256 with secret
    - PhonePe: SHA-256 of payload with salt
    - Stripe: HMAC-SHA256 with webhook secret
    - Cashfree: HMAC-SHA256 with secret key
    
    Args:
        provider: Payment provider name
        payload: Webhook payload as dict
        signature: Signature from provider header
        secret: Provider-specific secret key
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        logger.warning(f"No signature provided for {provider} webhook")
        return False
    
    if not secret:
        # In development mode, accept all signatures if no secret configured
        logger.debug(f"No secret configured for {provider}, accepting signature")
        return True
    
    try:
        # Convert payload to deterministic string for signing
        payload_str = json.dumps(payload, sort_keys=True)
        
        if provider == "razorpay":
            # Razorpay: HMAC-SHA256 of payload
            expected = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        
        elif provider == "phonepe":
            # PhonePe: SHA-256 with salt
            # PhonePe uses base64 encoding in production
            import base64
            hash_input = payload_str + secret
            hash_bytes = hashlib.sha256(hash_input.encode()).digest()
            expected = base64.b64encode(hash_bytes).decode()
            return hmac.compare_digest(signature, expected)
        
        elif provider == "stripe":
            # Stripe: HMAC-SHA256 with timestamp and payload
            # Stripe sends timestamped signatures
            if signature.startswith("t="):
                parts = signature.split(",")
                timestamp = parts[0][2:]
                sig = parts[1][3:] if len(parts) > 1 else ""
                signed_payload = f"{timestamp}.{payload_str}"
                expected = hmac.new(
                    secret.encode(),
                    signed_payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                return hmac.compare_digest(sig, expected)
        
        elif provider == "cashfree":
            # Cashfree: HMAC-SHA256
            expected = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        
        else:
            # Generic HMAC-SHA256 for unknown providers
            expected = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
    
    except Exception as e:
        logger.error(f"Signature verification error for {provider}: {e}")
        return False


def _get_provider_secret(provider: str) -> str:
    """
    Get webhook secret for a provider.
    
    In production, this should fetch from secure secret management
    (e.g., AWS Secrets Manager, HashiCorp Vault).
    
    Args:
        provider: Payment provider name
        
    Returns:
        Provider webhook secret
    """
    # In production, fetch from secure storage
    # For now, return empty string (development mode)
    secrets = {
        "razorpay": "",  # Set RAZORPAY_WEBHOOK_SECRET env var
        "phonepe": "",   # Set PHONEPE_WEBHOOK_SECRET env var
        "stripe": "",    # Set STRIPE_WEBHOOK_SECRET env var
        "cashfree": "",  # Set CASHFREE_WEBHOOK_SECRET env var
    }
    return secrets.get(provider, "")


# =============================================================================
# Idempotency Handling
# =============================================================================

async def _check_idempotency(
    db: Session,
    payment_id: str,
    status: str
) -> tuple[bool, Optional[Payment]]:
    """
    Check if webhook has already been processed (idempotency check).
    
    Args:
        db: Database session
        payment_id: Payment ID to check
        status: Incoming status from provider
        
    Returns:
        Tuple of (is_duplicate, existing_payment)
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    
    if not payment:
        return False, None
    
    # Check if this exact status has already been processed
    if payment.status == status:
        logger.info(
            f"Duplicate webhook detected for payment {payment_id}, "
            f"status already {status}"
        )
        return True, payment
    
    # Check if payment is in a terminal state
    terminal_statuses = [
        DBPaymentStatus.SUCCESS.value,
        DBPaymentStatus.FAILED.value,
        DBPaymentStatus.CANCELLED.value,
        DBPaymentStatus.REFUNDED.value,
    ]
    
    if payment.status in terminal_statuses:
        logger.info(
            f"Payment {payment_id} already in terminal state: {payment.status}"
        )
        return True, payment
    
    return False, payment


# =============================================================================
# Status Mapping
# =============================================================================

def _map_provider_status(provider: str, provider_status: str) -> str:
    """
    Map provider-specific status to our normalized status.
    
    Args:
        provider: Payment provider name
        provider_status: Provider's status string
        
    Returns:
        Normalized status string
    """
    # Normalize status to lowercase
    status = provider_status.lower().strip()
    
    # Common status mappings
    status_mappings = {
        # Success states
        "success": "success",
        "completed": "success",
        "captured": "success",
        "authorized": "success",
        "paid": "success",
        "payment_success": "success",
        
        # Failure states
        "failed": "failed",
        "failure": "failed",
        "declined": "failed",
        "rejected": "failed",
        "payment_failed": "failed",
        
        # Cancelled states
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "voided": "cancelled",
        
        # Pending states
        "pending": "pending",
        "processing": "processing",
        "initiated": "pending",
        "created": "pending",
        
        # Refunded states
        "refunded": "refunded",
        "refund_initiated": "refunded",
        "refund_completed": "refunded",
    }
    
    # Provider-specific mappings
    provider_mappings = {
        "razorpay": {
            "payment.captured": "success",
            "payment.authorized": "success",
            "payment.failed": "failed",
            "order.paid": "success",
        },
        "phonepe": {
            "SUCCESS": "success",
            "FAILED": "failed",
            "PENDING": "pending",
            "TIMEOUT": "failed",
        },
        "stripe": {
            "succeeded": "success",
            "payment_intent.succeeded": "success",
            "payment_intent.payment_failed": "failed",
            "charge.succeeded": "success",
            "charge.failed": "failed",
        },
        "cashfree": {
            "SUCCESS": "success",
            "FAILED": "failed",
            "PENDING": "pending",
            "CANCELLED": "cancelled",
        },
    }
    
    # Check provider-specific mappings first
    if provider in provider_mappings:
        if provider_status in provider_mappings[provider]:
            return provider_mappings[provider][provider_status]
    
    # Fall back to common mappings
    return status_mappings.get(status, "unknown")


# =============================================================================
# Payment Status Update Logic
# =============================================================================

async def _update_payment_status(
    db: Session,
    payment: Payment,
    payload: WebhookPayload,
    provider: str
) -> Booking:
    """
    Update payment status and trigger booking actions.
    
    Args:
        db: Database session
        payment: Payment record to update
        payload: Validated webhook payload
        provider: Payment provider name
        
    Returns:
        Updated booking record
    """
    # Map and update payment status
    new_status = _map_provider_status(provider, payload.status)
    payment.status = new_status
    payment.completed_at = datetime.now(timezone.utc)
    payment.provider = provider
    
    # Update transaction IDs
    if payload.transaction_id:
        payment.upi_tx_id = payload.transaction_id
    if payload.utr_number:
        payment.utr_number = payload.utr_number
    if payload.provider_reference:
        payment.provider_payment_id = payload.provider_reference
    
    # Store raw webhook payload
    payment.webhook_payload = payload.model_dump_json()
    payment.webhook_received_at = datetime.now(timezone.utc)
    
    # Get associated booking
    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    
    if not booking:
        logger.warning(f"Booking not found for payment {payment.id}")
        db.commit()
        return None
    
    # Trigger booking actions based on payment status
    from services.booking_service import get_booking_service
    from services.notification_service import get_notification_service
    
    booking_service = get_booking_service(db)
    notification_service = get_notification_service(db)
    
    if new_status == "success":
        # Confirm the booking
        payment_details = {
            "payment_id": payment.id,
            "upi_tx_id": payload.transaction_id,
            "utr_number": payload.utr_number,
            "amount": payload.amount,
        }
        
        await booking_service.confirm_booking(booking.id, payment_details)
        
        # Send confirmation notification
        await notification_service.queue_notification(
            booking.user_id,
            "booking_confirmed",
            {
                "booking_id": booking.id,
                "pnr": booking.pnr_number,
                "amount": payload.amount,
                "train": booking.train_number or "",
                "date": str(booking.travel_date),
            }
        )
        
        logger.info(f"Booking {booking.pnr_number} confirmed via {provider} webhook")
    
    elif new_status in ["failed", "cancelled"]:
        # Cancel the booking
        await booking_service.cancel_booking(
            booking.id,
            booking.user_id,
            reason=f"payment_{new_status}"
        )
        
        # Send failure notification
        await notification_service.queue_notification(
            booking.user_id,
            "payment_failed",
            {
                "booking_id": booking.id,
                "pnr": booking.pnr_number,
                "amount": payload.amount,
                "reason": payload.status,
            }
        )
        
        logger.info(f"Booking {booking.pnr_number} cancelled due to payment {new_status}")
    
    elif new_status == "refunded":
        # Handle refund
        booking.booking_status = "refunded"
        booking.refund_amount = payload.amount
        booking.refund_processed_at = datetime.now(timezone.utc)
        
        await notification_service.queue_notification(
            booking.user_id,
            "payment_refunded",
            {
                "booking_id": booking.id,
                "pnr": booking.pnr_number,
                "amount": payload.amount,
            }
        )
    
    db.commit()
    return booking


# =============================================================================
# Webhook Endpoints
# =============================================================================

@router.post(
    "/payment/{provider}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid payload"},
        401: {"model": ErrorResponse, "description": "Invalid signature"},
        404: {"model": ErrorResponse, "description": "Payment not found"},
        409: {"model": ErrorResponse, "description": "Duplicate webhook"},
    },
    summary="Handle payment provider webhooks",
    description="""
    Receive and process payment status updates from payment providers.
    
    This endpoint:
    1. Verifies the webhook signature for security
    2. Checks idempotency to prevent duplicate processing
    3. Updates the payment status
    4. Triggers booking confirmation or cancellation
    5. Sends notifications to the user
    
    Supported providers: razorpay, phonepe, stripe, cashfree, upi, card, net_banking
    """,
)
async def handle_payment_webhook(
    provider: str,
    request: Request,
    payload: WebhookPayload,
    x_signature: str = Header(None, alias="X-Signature"),
    x_webhook_id: str = Header(None, alias="X-Webhook-ID"),
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_hub_signature: str = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Handle payment provider webhook callbacks.
    
    Args:
        provider: Payment provider name (razorpay, phonepe, stripe, cashfree, etc.)
        payload: Validated webhook payload
        x_signature: Generic signature header
        x_webhook_id: Unique webhook ID for deduplication
        x_razorpay_signature: Razorpay-specific signature
        x_hub_signature: PhonePe-specific signature
        db: Database session
        
    Returns:
        WebhookResponse with processing status
    """
    # Get the appropriate signature header
    signature = (
        x_signature or
        x_razorpay_signature or
        x_hub_signature or
        ""
    )
    
    logger.info(
        f"Received webhook from {provider}: payment_id={payload.payment_id}, "
        f"status={payload.status}, amount={payload.amount}"
    )
    
    # Step 1: Verify webhook signature
    secret = _get_provider_secret(provider)
    if not _verify_signature(provider, payload.model_dump(), signature, secret):
        logger.warning(
            f"Invalid webhook signature from {provider} for payment {payload.payment_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Step 2: Check idempotency (has this payment already been processed?)
    is_duplicate, existing_payment = await _check_idempotency(
        db, payload.payment_id, payload.status
    )
    
    if is_duplicate and existing_payment:
        # Return success for duplicate webhook calls (idempotent)
        logger.info(
            f"Duplicate webhook for payment {payload.payment_id}, "
            f"status {payload.status}"
        )
        return WebhookResponse(
            status="already_processed",
            payment_id=payload.payment_id,
            booking_id=existing_payment.booking_id,
            message="Webhook already processed"
        )
    
    # Step 3: Get payment record
    payment = db.query(Payment).filter(Payment.id == payload.payment_id).first()
    
    if not payment:
        logger.warning(f"Payment not found: {payload.payment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Step 4: Update payment status and trigger booking actions
    try:
        booking = await _update_payment_status(db, payment, payload, provider)
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )
    
    return WebhookResponse(
        status="processed",
        payment_id=payload.payment_id,
        booking_id=payment.booking_id,
        message=f"Payment status updated to {payload.status}"
    )


@router.post(
    "/payment/{provider}/raw",
    summary="Handle raw webhook (JSON body as-is)",
    description="""
    Alternative endpoint that accepts raw JSON without Pydantic validation.
    Useful for providers with non-standard payload formats.
    """,
)
async def handle_payment_webhook_raw(
    provider: str,
    request: Request,
    x_signature: str = Header(None, alias="X-Signature"),
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_hub_signature: str = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Handle raw webhook without Pydantic validation.
    
    Use this endpoint when providers send non-standard payloads.
    """
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Get the appropriate signature header
    signature = x_signature or x_razorpay_signature or x_hub_signature or ""
    
    # Extract payment_id from various possible locations
    payment_id = (
        payload.get("payment_id") or
        payload.get("transaction_id") or
        payload.get("id") or
        payload.get("payment", {}).get("id") or
        payload.get("order", {}).get("id")
    )
    
    if not payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment ID not found in payload"
        )
    
    # Extract status
    status_str = (
        payload.get("status") or
        payload.get("event", "").replace("payment.", "") or
        payload.get("responseCode") or
        "unknown"
    )
    
    # Create payload object
    webhook_payload = WebhookPayload(
        payment_id=str(payment_id),
        status=status_str,
        amount=float(payload.get("amount", 0)),
        transaction_id=payload.get("transaction_id") or payload.get("upi_tx_id"),
        utr_number=payload.get("utr_number"),
        provider_reference=payload.get("provider_reference") or payload.get("provider_payment_id"),
    )
    
    # Delegate to main handler
    return await handle_payment_webhook(
        provider=provider,
        request=request,
        payload=webhook_payload,
        x_signature=signature,
        db=db,
    )


@router.get(
    "/health",
    summary="Webhook health check",
    description="Returns the health status of the webhook service.",
)
async def webhook_health():
    """Health check endpoint for webhook service."""
    return {
        "status": "healthy",
        "service": "payment-webhooks",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/payment/{provider}/health",
    summary="Provider-specific webhook health",
    description="Check if webhook endpoint is configured for a specific provider.",
)
async def provider_webhook_health(provider: str):
    """Check provider-specific webhook configuration."""
    secret = _get_provider_secret(provider)
    return {
        "provider": provider,
        "configured": bool(secret),
        "status": "healthy" if True else "misconfigured"
    }