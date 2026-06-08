from typing import Any, Dict, List
from database.models import BookingStatus, EscrowStatus


class BookingStateMachine:
    """Central booking state machine for next-action guidance and audit visibility."""

    BOOKING_STATUS_TRANSITIONS = {
        BookingStatus.PENDING.value.lower(): ["confirm", "cancel"],
        BookingStatus.RAC.value.lower(): ["confirm", "cancel"],
        BookingStatus.WAITLIST.value.lower(): ["confirm", "cancel"],
        BookingStatus.CONFIRMED.value.lower(): ["cancel"],
        BookingStatus.CANCELLED.value.lower(): [],
    }

    ESCROW_STATUS_TRANSITIONS = {
        EscrowStatus.CREATED.value.lower(): ["submit_utr", "cancel"],
        EscrowStatus.UTR_SUBMITTED.value.lower(): ["verify_payment", "mark_failed"],
        EscrowStatus.VERIFIED.value.lower(): ["complete_booking", "mark_failed"],
        EscrowStatus.BOOKING_INITIATED.value.lower(): ["complete_booking", "mark_failed"],
        EscrowStatus.COMPLETED.value.lower(): [],
        EscrowStatus.FAILED.value.lower(): ["refund", "resubmit_utr"],
        EscrowStatus.REFUNDED.value.lower(): [],
    }

    @classmethod
    def get_valid_next_actions(cls, booking: Any) -> List[str]:
        """Return valid next actions for the current booking state."""
        actions: List[str] = []
        booking_status = getattr(booking, "booking_status", None)
        escrow_status = getattr(booking, "escrow_status", None)

        booking_value = getattr(booking_status, "value", str(booking_status)).lower() if booking_status is not None else ""
        if booking_value and booking_value in cls.BOOKING_STATUS_TRANSITIONS:
            actions.extend(cls.BOOKING_STATUS_TRANSITIONS[booking_value])

        if escrow_status is not None:
            escrow_value = getattr(escrow_status, "value", str(escrow_status)).lower()
            if escrow_value in cls.ESCROW_STATUS_TRANSITIONS:
                actions.extend(cls.ESCROW_STATUS_TRANSITIONS[escrow_value])

        seen = set()
        deduped: List[str] = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                deduped.append(action)
        return deduped

    @classmethod
    def get_current_state(cls, booking: Any) -> Dict[str, str]:
        booking_status = getattr(booking, "booking_status", None)
        escrow_status = getattr(booking, "escrow_status", None)
        return {
            "booking_status": getattr(booking_status, "value", str(booking_status)) if booking_status is not None else "unknown",
            "escrow_status": getattr(escrow_status, "value", str(escrow_status)) if escrow_status is not None else "unknown",
        }

    @classmethod
    def describe_next_actions(cls, booking: Any) -> Dict[str, Any]:
        """Provide structured next-action guidance for UI and workflow orchestration."""
        return {
            "current_state": cls.get_current_state(booking),
            "valid_next_actions": cls.get_valid_next_actions(booking),
        }
