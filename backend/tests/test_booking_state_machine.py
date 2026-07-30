from collections import namedtuple

from services.booking_state_machine import BookingStateMachine

DummyBooking = namedtuple("DummyBooking", ["booking_status", "escrow_status"])


def test_get_valid_next_actions_for_pending_booking():
    booking = DummyBooking(booking_status="pending", escrow_status="created")
    actions = BookingStateMachine.get_valid_next_actions(booking)

    assert "confirm" in actions
    assert "cancel" in actions
    assert "submit_utr" in actions


def test_get_current_state_returns_structured_state():
    booking = DummyBooking(booking_status="confirmed", escrow_status="completed")
    state = BookingStateMachine.get_current_state(booking)

    assert state["booking_status"] == "confirmed"
    assert state["escrow_status"] == "completed"


def test_describe_next_actions_includes_state_and_actions():
    booking = DummyBooking(booking_status="pending", escrow_status="created")
    description = BookingStateMachine.describe_next_actions(booking)

    assert description["current_state"]["booking_status"] == "pending"
    assert "confirm" in description["valid_next_actions"]
