#!/usr/bin/env python3
"""
Feature #1 Verification Script
Tests the complete booking & payment flow implementation
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))
sys.path.insert(0, str(backend_root.parent))

# ============================================================================
# VERIFICATION TESTS
# ============================================================================

class FeatureVerification:
    """Verify Feature #1 implementation."""

    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []

    def log_pass(self, test_name: str):
        """Log a passing test."""
        self.tests_passed += 1
        print(f"✓ {test_name}")

    def log_fail(self, test_name: str, reason: str):
        """Log a failing test."""
        self.tests_failed += 1
        self.errors.append((test_name, reason))
        print(f"✗ {test_name}: {reason}")

    def verify_imports(self):
        """Verify all required imports work."""
        print("\n" + "="*70)
        print("STEP 1: VERIFY IMPORTS")
        print("="*70)

        try:
            from api.booking_routes import router as booking_router
            self.log_pass("Import booking_routes router")
        except Exception as e:
            self.log_fail("Import booking_routes router", str(e))
            return False

        try:
            from api.payment_webhook import router as webhook_router
            self.log_pass("Import payment_webhook router")
        except Exception as e:
            self.log_fail("Import payment_webhook router", str(e))
            return False

        try:
            from services.booking_service import get_booking_service, BookingService
            self.log_pass("Import BookingService and factory function")
        except Exception as e:
            self.log_fail("Import BookingService", str(e))
            return False

        try:
            from services.payment_service import get_payment_service, PaymentService
            self.log_pass("Import PaymentService and factory function")
        except Exception as e:
            self.log_fail("Import PaymentService", str(e))
            return False

        try:
            from schemas.booking import (
                BookingRequest, BookingResponse, BookingStatus,
                PassengerDetails
            )
            self.log_pass("Import booking schemas")
        except Exception as e:
            self.log_fail("Import booking schemas", str(e))
            return False

        try:
            from schemas.payment import (
                PaymentStatus, PaymentResponse, PaymentVerifyRequest
            )
            self.log_pass("Import payment schemas")
        except Exception as e:
            self.log_fail("Import payment schemas", str(e))
            return False

        return True

    def verify_endpoints(self):
        """Verify endpoint structure."""
        print("\n" + "="*70)
        print("STEP 2: VERIFY ENDPOINT STRUCTURE")
        print("="*70)

        try:
            from api.booking_routes import router as booking_router

            # Check router has expected routes
            routes = [route.path for route in booking_router.routes]

            expected_patterns = [
                "/{booking_id}/payment/initiate",
                "/{booking_id}/payment/verify",
                "/{booking_id}",
            ]

            for pattern in expected_patterns:
                if any(pattern in route for route in routes):
                    self.log_pass(f"Endpoint exists: {pattern}")
                else:
                    self.log_fail(f"Endpoint exists: {pattern}", "Route not found")

        except Exception as e:
            self.log_fail("Verify endpoints", str(e))

    def verify_schemas(self):
        """Verify Pydantic schemas."""
        print("\n" + "="*70)
        print("STEP 3: VERIFY SCHEMAS")
        print("="*70)

        try:
            from schemas.booking import BookingRequest, PassengerDetails
            from datetime import datetime

            # Test PassengerDetails validation
            passenger = PassengerDetails(
                full_name="Test User",
                age=30,
                gender="M",
                phone_number="9876543210",
                email="test@example.com"
            )
            self.log_pass("PassengerDetails schema validates correctly")
        except Exception as e:
            self.log_fail("PassengerDetails schema", str(e))

        try:
            from schemas.booking import BookingRequest

            # Test booking request (should fail without required fields)
            try:
                booking = BookingRequest()
                self.log_fail("BookingRequest validation", "Should require fields")
            except:
                self.log_pass("BookingRequest requires all fields")
        except Exception as e:
            self.log_fail("BookingRequest schema", str(e))

        try:
            from schemas.payment import PaymentVerifyRequest

            # Test payment verify request
            verify_req = PaymentVerifyRequest(
                razorpay_order_id="order_123",
                razorpay_payment_id="pay_456",
                razorpay_signature="sig_789"
            )
            self.log_pass("PaymentVerifyRequest schema validates correctly")
        except Exception as e:
            self.log_fail("PaymentVerifyRequest schema", str(e))

    def verify_response_fields(self):
        """Verify response field names."""
        print("\n" + "="*70)
        print("STEP 4: VERIFY RESPONSE FIELD NAMES")
        print("="*70)

        try:
            from schemas.booking import BookingResponse

            # Check BookingResponse has expected fields
            response = BookingResponse(
                booking_id="book_123",
                pnr_number="1234567890",
                status="initiated",
                total_amount=5000.0,
                seats_allocated=[]
            )

            # Verify field names
            data = response.model_dump()
            expected_fields = ["booking_id", "pnr_number", "status", "total_amount"]

            for field in expected_fields:
                if field in data:
                    self.log_pass(f"BookingResponse has field: {field}")
                else:
                    self.log_fail(f"BookingResponse field: {field}", "Field missing")

        except Exception as e:
            self.log_fail("Verify response fields", str(e))

        # Verify payment response uses correct field names
        try:
            # Just check that the response would have the right field names
            # by checking the endpoint code for razorpay_order_id
            with open(backend_root / "api" / "booking_routes.py") as f:
                code = f.read()
                if "razorpay_order_id" in code and "amount_paise" in code:
                    self.log_pass("Payment response uses correct field names")
                else:
                    self.log_fail("Payment response field names", "Not using razorpay_order_id/amount_paise")
        except Exception as e:
            self.log_fail("Check payment response field names", str(e))

    def verify_database_models(self):
        """Verify database models exist."""
        print("\n" + "="*70)
        print("STEP 5: VERIFY DATABASE MODELS")
        print("="*70)

        try:
            from database.models.core import Booking, BookingIdempotency, BookingAuditLog, BookingMonitor
            self.log_pass("Booking model exists")
            self.log_pass("BookingIdempotency model exists")
            self.log_pass("BookingAuditLog model exists")
            self.log_pass("BookingMonitor model exists")
        except ImportError as e:
            self.log_fail("Database models", str(e))

    def verify_factory_functions(self):
        """Verify factory functions exist and work."""
        print("\n" + "="*70)
        print("STEP 6: VERIFY FACTORY FUNCTIONS")
        print("="*70)

        try:
            from services.booking_service import get_booking_service
            # Just verify the function exists and is callable
            if callable(get_booking_service):
                self.log_pass("get_booking_service factory function exists")
            else:
                self.log_fail("get_booking_service", "Not callable")
        except ImportError as e:
            self.log_fail("get_booking_service import", str(e))

        try:
            from services.payment_service import get_payment_service
            if callable(get_payment_service):
                self.log_pass("get_payment_service factory function exists")
            else:
                self.log_fail("get_payment_service", "Not callable")
        except ImportError as e:
            self.log_fail("get_payment_service import", str(e))

    def verify_file_structure(self):
        """Verify expected files exist."""
        print("\n" + "="*70)
        print("STEP 7: VERIFY FILE STRUCTURE")
        print("="*70)

        files_to_check = [
            ("backend/api/booking_routes.py", "Booking routes"),
            ("backend/api/payment_webhook.py", "Payment webhook"),
            ("backend/services/booking_service.py", "Booking service factory"),
            ("backend/services/payment_service.py", "Payment service"),
            ("backend/schemas/booking.py", "Booking schemas"),
            ("backend/schemas/payment.py", "Payment schemas"),
            ("backend/tests/test_feature_1_booking_payment.py", "Feature #1 test suite"),
            ("frontend/src/store/useBookingStore.ts", "Booking store"),
            ("frontend/src/hooks/useBookingFlow.ts", "Booking flow hook"),
        ]

        for filepath, description in files_to_check:
            full_path = backend_root.parent / filepath
            if full_path.exists():
                self.log_pass(f"{description} exists")
            else:
                self.log_fail(f"{description} exists", f"File not found: {filepath}")

    def verify_app_registration(self):
        """Verify routers are registered in app.py."""
        print("\n" + "="*70)
        print("STEP 8: VERIFY APP ROUTER REGISTRATION")
        print("="*70)

        try:
            with open(backend_root / "app.py") as f:
                app_code = f.read()

            if "_include(\"api.booking_routes\"" in app_code:
                self.log_pass("booking_routes registered in app.py")
            else:
                self.log_fail("booking_routes registration", "Not found in app.py")

            if "_include(\"api.payment_webhook\"" in app_code:
                self.log_pass("payment_webhook registered in app.py")
            else:
                self.log_fail("payment_webhook registration", "Not found in app.py")
        except Exception as e:
            self.log_fail("Verify app registration", str(e))

    def run_all_verifications(self):
        """Run all verification tests."""
        print("\n")
        print("╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "FEATURE #1: BOOKING & PAYMENT - VERIFICATION SUITE".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")

        self.verify_imports()
        self.verify_endpoints()
        self.verify_schemas()
        self.verify_response_fields()
        self.verify_database_models()
        self.verify_factory_functions()
        self.verify_file_structure()
        self.verify_app_registration()

        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("VERIFICATION SUMMARY")
        print("="*70)

        total = self.tests_passed + self.tests_failed
        percentage = (self.tests_passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {self.tests_passed} ✓")
        print(f"Failed: {self.tests_failed} ✗")
        print(f"Success Rate: {percentage:.1f}%")

        if self.errors:
            print("\n" + "─"*70)
            print("FAILED TESTS:")
            print("─"*70)
            for test_name, reason in self.errors:
                print(f"\n  ✗ {test_name}")
                print(f"    Reason: {reason}")

        print("\n" + "="*70)

        if self.tests_failed == 0:
            print("✓ ALL VERIFICATIONS PASSED - Implementation is ready for testing!")
        else:
            print(f"✗ {self.tests_failed} verification(s) failed - Review issues above")

        print("="*70 + "\n")

        return self.tests_failed == 0


if __name__ == "__main__":
    verifier = FeatureVerification()
    success = verifier.run_all_verifications()
    sys.exit(0 if success else 1)
