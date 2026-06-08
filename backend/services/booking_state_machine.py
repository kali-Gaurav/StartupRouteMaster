from enum import Enum
from typing import Any, List
from core.engines.booking_state import BookingStateMachine as CoreBookingStateMachine


class BookingFlowState(Enum):
    SEARCH = "SEARCH"
    SELECTED = "SELECTED"
    PASSENGER_INFO = "PASSENGER_INFO"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    CONFIRMED = "CONFIRMED"
    TICKETED = "TICKETED"
    CANCELLED = "CANCELLED"


class BookingStateMachine(CoreBookingStateMachine):
    """Real FSM for the booking workflow.
    
    States: SEARCH -> SELECTED -> PASSENGER_INFO -> PAYMENT_PENDING -> CONFIRMED -> TICKETED -> CANCELLED
    """

    FLOW_TRANSITIONS = {
        BookingFlowState.SEARCH: [BookingFlowState.SELECTED],
        BookingFlowState.SELECTED: [BookingFlowState.PASSENGER_INFO, BookingFlowState.CANCELLED],
        BookingFlowState.PASSENGER_INFO: [BookingFlowState.PAYMENT_PENDING, BookingFlowState.CANCELLED],
        BookingFlowState.PAYMENT_PENDING: [BookingFlowState.CONFIRMED, BookingFlowState.CANCELLED],
        BookingFlowState.CONFIRMED: [BookingFlowState.TICKETED, BookingFlowState.CANCELLED],
        BookingFlowState.TICKETED: [BookingFlowState.CANCELLED],
        BookingFlowState.CANCELLED: [],
    }

    @classmethod
    def get_valid_next_states(cls, current_state: BookingFlowState) -> List[BookingFlowState]:
        """Return valid next states from the current state."""
        return cls.FLOW_TRANSITIONS.get(current_state, [])

    @classmethod
    def is_transition_valid(cls, from_state: BookingFlowState, to_state: BookingFlowState) -> bool:
        """Check if a transition is valid."""
        return to_state in cls.get_valid_next_states(from_state)

    @classmethod
    def transition(cls, booking: Any, to_state: BookingFlowState) -> None:
        """Transition a booking to a new state with validation and hooks."""
        current_state_str = getattr(booking, "flow_state", "SEARCH")
        try:
            current_state = BookingFlowState(current_state_str)
        except ValueError:
            current_state = BookingFlowState.SEARCH

        if not cls.is_transition_valid(current_state, to_state):
            raise ValueError(f"Invalid state transition from {current_state.value} to {to_state.value}")

        # Execute exit hook
        cls.on_exit(booking, current_state)

        # Set new state
        setattr(booking, "flow_state", to_state.value)

        # Execute enter hook
        cls.on_enter(booking, to_state)

    @classmethod
    def on_enter(cls, booking: Any, state: BookingFlowState) -> None:
        """Hook called when entering a state."""
        # Implement specific logic for states if needed
        pass

    @classmethod
    def on_exit(cls, booking: Any, state: BookingFlowState) -> None:
        """Hook called when exiting a state."""
        pass
