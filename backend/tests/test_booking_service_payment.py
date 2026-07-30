import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from services.booking_service import BookingService
from database.models import Payment, Booking, EscrowStatus, SeatInventory


def test_confirm_booking_payment_marks_booking_completed(monkeypatch):
    payment = MagicMock()
    payment.booking_id = "booking_123"
    payment.status = "pending"
    payment.razorpay_payment_id = None

    booking = MagicMock()
    booking.id = "booking_123"
    booking.booking_status = "pending"
    booking.escrow_status = EscrowStatus.CREATED
    booking.payment_status = "pending"
    booking.escrow_message = None
    booking.pnr_number = "PNR123"
    booking.user_id = "user_1"

    payment_query = MagicMock()
    payment_query.filter.return_value.first.return_value = payment

    booking_query = MagicMock()
    booking_query.filter.return_value.first.return_value = booking

    def query_side_effect(model):
        if model is Payment:
            return payment_query
        if model is Booking:
            return booking_query
        return MagicMock()

    db = MagicMock()
    db.query.side_effect = query_side_effect
    db.commit = MagicMock()
    db.rollback = MagicMock()

    service = BookingService(db)
    monkeypatch.setattr(service, "confirm_booking", lambda booking_id, ip_address=None: True)

    result = service.confirm_booking_payment("order_abc", "pay_ghi", "completed")

    assert result is True
    assert payment.razorpay_payment_id == "pay_ghi"
    assert payment.status == "completed"
    assert booking.payment_status == "completed"
    assert booking.escrow_status == EscrowStatus.COMPLETED


def test_reserve_seat_inventory_locks_available_seat():
    booking = MagicMock()
    booking.id = "booking_456"
    booking.route_id = "route_1"
    booking.travel_date = "2026-05-01"

    inventory = MagicMock(spec=SeatInventory)
    inventory.available_seats = 2
    inventory.locked_until = None
    inventory.locked_by_booking_id = None

    seat_query = MagicMock()
    seat_query.filter.return_value.first.return_value = inventory

    def query_side_effect(model):
        if model is SeatInventory:
            return seat_query
        return MagicMock()

    db = MagicMock()
    db.query.side_effect = query_side_effect
    db.flush = MagicMock()

    service = BookingService(db)
    service.reserve_seat_inventory(booking)

    assert inventory.available_seats == 1
    assert inventory.locked_by_booking_id == booking.id
    assert inventory.locked_until is not None
    assert inventory.locked_until > datetime.utcnow()
    db.flush.assert_called_once()
