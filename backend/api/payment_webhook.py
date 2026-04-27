"""
Versioned payment webhook endpoint for booking/payment reconciliation.

The handler is intentionally provider-neutral: Razorpay signatures are verified
when the provider is `razorpay`, while internal/bank simulators can post the same
normalized payload during tests or operations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from database.models import Booking, EscrowStatus, Payment, PaymentTransaction, WebhookEvent
from services.booking_service import BookingService
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class PaymentWebhookPayload(BaseModel):
    payment_id: Optional[str] = Field(None, description="Internal payment record ID or provider payment ID")
    booking_id: Optional[str] = None
    order_id: Optional[str] = None
    provider_reference: Optional[str] = None
    utr_number: Optional[str] = None
    amount: float = Field(0.0, ge=0)
    method: str = "UPI"
    status: str = "success"
    event_id: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


def _normalize_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"captured", "paid", "completed", "success", "succeeded"}:
        return "success"
    if normalized in {"failed", "failure", "cancelled", "canceled", "declined"}:
        return "failed"
    if normalized in {"refunded", "refund"}:
        return "refunded"
    return normalized or "pending"


def _extract_payload(provider: str, raw_body: bytes) -> PaymentWebhookPayload:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON payload") from exc

    if provider.lower() == "razorpay" and "payload" in body:
        payment_entity = (
            body.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        order_entity = (
            body.get("payload", {})
            .get("order", {})
            .get("entity", {})
        )
        notes = payment_entity.get("notes") or order_entity.get("notes") or {}
        return PaymentWebhookPayload(
            payment_id=payment_entity.get("id"),
            booking_id=notes.get("booking_id"),
            order_id=payment_entity.get("order_id") or order_entity.get("id"),
            provider_reference=payment_entity.get("id") or order_entity.get("id"),
            amount=float(payment_entity.get("amount") or order_entity.get("amount") or 0) / 100.0,
            method=str(payment_entity.get("method") or "RAZORPAY").upper(),
            status=_normalize_status(payment_entity.get("status") or body.get("event", "")),
            event_id=body.get("id") or body.get("event") or payment_entity.get("id"),
            raw=body,
        )
    return PaymentWebhookPayload(**body)


def _verify_provider_signature(provider: str, request: Request, body: bytes) -> None:
    if provider.lower() != "razorpay":
        return
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Razorpay webhook signature")
    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")


def _find_booking(db: Session, payload: PaymentWebhookPayload) -> Optional[Booking]:
    if payload.booking_id:
        booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
        if booking:
            return booking
    if payload.order_id:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == payload.order_id).first()
        if payment and payment.booking_id:
            return db.query(Booking).filter(Booking.id == payment.booking_id).first()
    return None


def _log_webhook_event(db: Session, event_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    if existing_event:
        return

    db.add(WebhookEvent(id=event_id, event_type=event_type, payload=payload))


@router.post("/payment/{provider}")
async def handle_payment_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = await request.body()
    _verify_provider_signature(provider, request, body)

    payload = _extract_payload(provider, body)
    payment_status = _normalize_status(payload.status)
    event_ref = payload.event_id or payload.provider_reference or payload.payment_id or payload.order_id
    event_id = f"{provider.lower()}:{event_ref}" if event_ref else None

    if event_id:
        existing_webhook = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if existing_webhook:
            return {"status": "accepted", "idempotent": True, "event_id": event_id}

    existing = None
    if event_ref:
        existing = db.query(PaymentTransaction).filter(
            PaymentTransaction.provider_reference == event_ref
        ).first()
    if existing and existing.status == payment_status:
        if event_id:
            _log_webhook_event(db, event_id, f"payment.{provider.lower()}", payload.raw)
            db.commit()
        return {"status": "accepted", "idempotent": True, "payment_status": existing.status}

    booking = _find_booking(db, payload)
    if not booking:
        raise HTTPException(status_code=404, detail="No booking matched this payment webhook")

    transaction = existing or PaymentTransaction(
        payment_id=str(payload.payment_id or event_ref or f"wh_{datetime.utcnow().timestamp()}"),
        booking_id=str(booking.id),
        amount=float(payload.amount or booking.amount_paid or 0.0),
        method=payload.method.upper(),
        provider_reference=event_ref,
        utr_number=payload.utr_number,
    )
    transaction.status = payment_status
    transaction.utr_number = payload.utr_number or transaction.utr_number
    if existing is None:
        db.add(transaction)

    if payload.utr_number:
        booking.utr_number = payload.utr_number

    if payment_status == "success":
        booking.escrow_status = EscrowStatus.COMPLETED
        booking.escrow_message = "Payment confirmed by webhook."
        BookingService(db).confirm_booking(str(booking.id))
    elif payment_status in {"failed", "cancelled"}:
        booking.escrow_status = EscrowStatus.FAILED
        booking.escrow_message = "Payment failed or was cancelled."
        BookingService(db).cancel_booking(
            str(booking.id),
            reason="Payment failed or was cancelled.",
            user_id=str(booking.user_id) if booking.user_id else None,
        )
    elif payment_status == "refunded":
        booking.escrow_status = EscrowStatus.REFUNDED
        booking.escrow_message = "Payment refunded."
        BookingService(db).cancel_booking(
            str(booking.id),
            reason="Payment refunded.",
            user_id=str(booking.user_id) if booking.user_id else None,
        )

    if payload.order_id:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == payload.order_id).first()
        if payment:
            payment.status = "completed" if payment_status == "success" else payment_status
            payment.razorpay_payment_id = payload.provider_reference or payment.razorpay_payment_id

    if event_id:
        _log_webhook_event(db, event_id, f"payment.{provider.lower()}", payload.raw)

    db.commit()
    logger.info("Payment webhook processed provider=%s booking=%s status=%s", provider, booking.id, payment_status)
    return {
        "status": "accepted",
        "booking_id": str(booking.id),
        "payment_status": payment_status,
        "idempotent": False,
        "event_id": event_id,
    }


__all__ = ["router", "PaymentWebhookPayload"]
