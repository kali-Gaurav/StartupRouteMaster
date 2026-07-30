"""
Unit tests for payment webhook normalization and idempotency handling.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from unittest.mock import MagicMock

backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api.payment_webhook import _normalize_status, _extract_payload, handle_payment_webhook
from database.models import PaymentTransaction


class DummyRequest:
    def __init__(self, headers, body_bytes):
        self.headers = headers
        self._body = body_bytes

    async def body(self):
        return self._body


def test_normalize_status_variants():
    assert _normalize_status("captured") == "success"
    assert _normalize_status("paid") == "success"
    assert _normalize_status("failed") == "failed"
    assert _normalize_status("refund") == "refunded"
    assert _normalize_status("unknown") == "unknown"


def test_extract_payload_razorpay_hydrates_booking_info():
    payload = {
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "amount": 55000,
                    "status": "captured",
                    "method": "upi",
                    "order_id": "order_456",
                    "notes": {"booking_id": "booking_789"},
                }
            },
            "order": {
                "entity": {
                    "id": "order_456",
                    "amount": 55000,
                    "notes": {"booking_id": "booking_789"},
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    result = _extract_payload("razorpay", body)

    assert result.booking_id == "booking_789"
    assert result.order_id == "order_456"
    assert result.payment_id == "pay_123"
    assert result.provider_reference == "pay_123"
    assert result.amount == 550.0
    assert result.status == "success"


def test_extract_payload_razorpay_prefers_webhook_event_id():
    payload = {
        "id": "event_abc",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "amount": 55000,
                    "status": "captured",
                    "method": "upi",
                    "order_id": "order_456",
                    "notes": {"booking_id": "booking_789"},
                }
            },
            "order": {
                "entity": {
                    "id": "order_456",
                    "amount": 55000,
                    "notes": {"booking_id": "booking_789"},
                }
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    result = _extract_payload("razorpay", body)

    assert result.event_id == "event_abc"
    assert result.provider_reference == "pay_123"


def test_handle_payment_webhook_duplicate_event_is_idempotent(monkeypatch):
    payload = {
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_123",
                    "amount": 55000,
                    "status": "captured",
                    "method": "upi",
                    "order_id": "order_456",
                    "notes": {"booking_id": "booking_789"},
                }
            }
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    request = DummyRequest({"X-Razorpay-Signature": "sig"}, body_bytes)

    # Mock DB behavior for idempotent duplicate handling
    existing_txn = MagicMock(status="success")
    txn_query = MagicMock()
    txn_query.filter.return_value = txn_query
    txn_query.first.return_value = existing_txn

    payment_query = MagicMock()
    payment_query.filter.return_value = payment_query
    payment_query.first.return_value = None

    def query_side_effect(model):
        if model is PaymentTransaction:
            return txn_query
        return payment_query

    db = MagicMock()
    db.query.side_effect = query_side_effect

    monkeypatch.setattr("api.payment_webhook._verify_provider_signature", lambda provider, request, body: None)

    result = asyncio.run(handle_payment_webhook("razorpay", request, db))

    assert result["idempotent"] is True
    assert result["status"] == "accepted"
    assert result["payment_status"] == "success"


def test_handle_payment_webhook_duplicate_webhook_event_is_idempotent(monkeypatch):
    payload = {
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_456",
                    "amount": 42500,
                    "status": "captured",
                    "method": "upi",
                    "order_id": "order_789",
                    "notes": {"booking_id": "booking_123"},
                }
            }
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    request = DummyRequest({"X-Razorpay-Signature": "sig"}, body_bytes)

    existing_event = MagicMock()
    webhook_query = MagicMock()
    webhook_query.filter.return_value = webhook_query
    webhook_query.first.return_value = existing_event

    payment_query = MagicMock()
    payment_query.filter.return_value = payment_query
    payment_query.first.return_value = None

    def query_side_effect(model):
        if model.__name__ == "WebhookEvent":
            return webhook_query
        return payment_query

    db = MagicMock()
    db.query.side_effect = query_side_effect

    monkeypatch.setattr("api.payment_webhook._verify_provider_signature", lambda provider, request, body: None)

    result = asyncio.run(handle_payment_webhook("razorpay", request, db))

    assert result["idempotent"] is True
    assert result["status"] == "accepted"
    assert result["event_id"].startswith("razorpay:")
