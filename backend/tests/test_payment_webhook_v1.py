import pytest
from fastapi import HTTPException

from api.payment_webhook import _extract_payload, _normalize_status


def test_extracts_razorpay_payment_payload_with_booking_note():
    payload = b'''{
      "event": "payment.captured",
      "payload": {
        "payment": {
          "entity": {
            "id": "pay_123",
            "order_id": "order_123",
            "amount": 12345,
            "method": "upi",
            "status": "captured",
            "notes": {"booking_id": "booking_123"}
          }
        }
      }
    }'''

    result = _extract_payload("razorpay", payload)

    assert result.booking_id == "booking_123"
    assert result.order_id == "order_123"
    assert result.provider_reference == "pay_123"
    assert result.amount == 123.45
    assert result.method == "UPI"
    assert result.status == "success"


def test_extracts_provider_neutral_payload():
    payload = b'''{
      "booking_id": "booking_456",
      "provider_reference": "bank_ref_456",
      "amount": 500.0,
      "method": "upi",
      "status": "failed",
      "utr_number": "123456789012"
    }'''

    result = _extract_payload("bank", payload)

    assert result.booking_id == "booking_456"
    assert result.provider_reference == "bank_ref_456"
    assert result.amount == 500.0
    assert result.status == "failed"
    assert result.utr_number == "123456789012"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("captured", "success"),
        ("paid", "success"),
        ("declined", "failed"),
        ("refunded", "refunded"),
        ("", "pending"),
    ],
)
def test_normalizes_payment_statuses(raw, expected):
    assert _normalize_status(raw) == expected


def test_rejects_invalid_webhook_json():
    with pytest.raises(HTTPException) as exc:
        _extract_payload("bank", b"{not-json")

    assert exc.value.status_code == 400
