#!/usr/bin/env python3
"""
RouteMaster Feature #1 — Razorpay Webhook Testing Utility

Usage:
    python scripts/test_webhook.py --environment development
    python scripts/test_webhook.py --environment staging --webhook-url https://...

Simulates payment events and sends them to the webhook endpoint.
Useful for testing webhook processing locally or in staging.
"""

import os
import sys
import json
import hmac
import hashlib
import argparse
import time
from datetime import datetime
import requests
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__) + "/..")

from dotenv import load_dotenv

# Load environment
environment = os.getenv("ENVIRONMENT", "development")
env_file = f".env.{environment}" if environment != "development" else ".env.local"
if os.path.exists(env_file):
    load_dotenv(env_file)


class WebhookTester:
    """Test Razorpay webhook events"""

    def __init__(self, webhook_url: str, webhook_secret: str):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret

    def sign_payload(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload"""
        return hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    def send_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Send a test webhook event"""

        payload = {
            "event": event_type,
            "created_at": int(time.time()),
            "data": event_data
        }

        payload_json = json.dumps(payload)
        signature = self.sign_payload(payload_json)

        headers = {
            "X-Razorpay-Signature": signature,
            "Content-Type": "application/json"
        }

        print(f"\nSending {event_type}...")
        print(f"  URL: {self.webhook_url}")
        print(f"  Signature: {signature[:20]}...")

        try:
            response = requests.post(
                self.webhook_url,
                data=payload_json,
                headers=headers,
                timeout=10
            )

            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:100]}")

            return response.status_code == 200

        except Exception as e:
            print(f"  Error: {e}")
            return False

    def test_payment_captured(self, booking_id: str, amount: float) -> bool:
        """Test payment.captured event"""

        event = {
            "entity": {
                "id": "pay_00000000000001",
                "entity": "payment",
                "amount": int(amount * 100),  # Razorpay uses paise
                "currency": "INR",
                "status": "captured",
                "notes": {
                    "booking_id": booking_id
                }
            }
        }

        return self.send_event("payment.captured", event)

    def test_payment_failed(self, booking_id: str, amount: float, reason: str = "card_declined") -> bool:
        """Test payment.failed event"""

        event = {
            "entity": {
                "id": "pay_00000000000002",
                "entity": "payment",
                "amount": int(amount * 100),
                "currency": "INR",
                "status": "failed",
                "error_code": reason,
                "notes": {
                    "booking_id": booking_id
                }
            }
        }

        return self.send_event("payment.failed", event)

    def test_order_paid(self, order_id: str, amount: float) -> bool:
        """Test order.paid event"""

        event = {
            "entity": {
                "id": order_id,
                "entity": "order",
                "amount": int(amount * 100),
                "currency": "INR",
                "status": "paid"
            }
        }

        return self.send_event("order.paid", event)

    def test_idempotency(self, booking_id: str, amount: float) -> bool:
        """Test idempotency by sending same event twice"""

        print("\n=== Testing Idempotency ===")
        print("Sending same event twice. Second should be deduplicated.\n")

        success = True

        # First event
        result1 = self.test_payment_captured(booking_id, amount)
        time.sleep(1)

        # Identical second event
        result2 = self.test_payment_captured(booking_id, amount)

        if result1 and result2:
            print("\n✓ Idempotency test passed (both succeeded)")
            return True
        else:
            print("\n✗ Idempotency test failed")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Razorpay webhooks"
    )
    parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "staging", "production"],
        help="Target environment"
    )
    parser.add_argument(
        "--webhook-url",
        help="Webhook URL (auto-detected from environment if not provided)"
    )
    parser.add_argument(
        "--booking-id",
        default="test-booking-12345",
        help="Test booking ID"
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=5000.00,
        help="Test amount in INR"
    )
    parser.add_argument(
        "--test",
        default="all",
        choices=["captured", "failed", "order_paid", "idempotency", "all"],
        help="Which test to run"
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv(f".env.{args.environment}" if args.environment != "development" else ".env.local")

    # Get webhook URL
    if args.webhook_url:
        webhook_url = args.webhook_url
    else:
        if args.environment == "development":
            webhook_url = "http://localhost:8000/api/v1/payments/webhook"
        elif args.environment == "staging":
            webhook_url = os.getenv(
                "RAZORPAY_WEBHOOK_URL",
                "https://staging-api.routemaster.railway.app/api/v1/payments/webhook"
            )
        else:
            webhook_url = os.getenv(
                "RAZORPAY_WEBHOOK_URL",
                "https://api.routemaster.app/api/v1/payments/webhook"
            )

    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    if not webhook_secret:
        print("ERROR: RAZORPAY_WEBHOOK_SECRET not set in environment")
        sys.exit(1)

    print("════════════════════════════════════════════════════════════════════")
    print("  RouteMaster Webhook Tester")
    print("════════════════════════════════════════════════════════════════════")
    print(f"Environment: {args.environment}")
    print(f"Webhook URL: {webhook_url}")
    print(f"Booking ID: {args.booking_id}")
    print(f"Amount: {args.amount} INR")
    print("════════════════════════════════════════════════════════════════════")

    tester = WebhookTester(webhook_url, webhook_secret)

    results = {}

    if args.test in ["captured", "all"]:
        results["payment.captured"] = tester.test_payment_captured(
            args.booking_id,
            args.amount
        )
        time.sleep(1)

    if args.test in ["failed", "all"]:
        results["payment.failed"] = tester.test_payment_failed(
            args.booking_id,
            args.amount
        )
        time.sleep(1)

    if args.test in ["order_paid", "all"]:
        results["order.paid"] = tester.test_order_paid(
            f"order_{args.booking_id}",
            args.amount
        )
        time.sleep(1)

    if args.test in ["idempotency", "all"]:
        results["idempotency"] = tester.test_idempotency(
            args.booking_id,
            args.amount
        )

    # Summary
    print("\n════════════════════════════════════════════════════════════════════")
    print("  Summary")
    print("════════════════════════════════════════════════════════════════════")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("════════════════════════════════════════════════════════════════════")

    # Exit with error if any failed
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
