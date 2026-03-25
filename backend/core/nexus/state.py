import enum
import logging
from datetime import datetime

logger = logging.getLogger("nexus.state")

class NexusState(enum.Enum):
    OFFLINE = "OFFLINE"
    BOOTING = "BOOTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"  # Security Breach or Critical Failure
    SAFE_MODE = "SAFE_MODE" # Maintenance mode

class NexusStateManager:
    """[Task 1.1] Centrally coordinates the operational lifecycle of RouteMaster V3."""
    
    def __init__(self):
        self._current_state = NexusState.OFFLINE
        self._last_state_change = datetime.utcnow()
        self._boot_time = None
        self._halt_reason = None
        
    @property
    def current_state(self) -> NexusState:
        return self._current_state
        
    def set_state(self, new_state: NexusState, reason: str = None):
        if new_state == self._current_state:
            return
            
        logger.info(f"🔄 [NEXUS STATE] Changing: {self._current_state.value} -> {new_state.value} | Reason: {reason or 'N/A'}")
        
        if new_state == NexusState.READY and not self._boot_time:
            self._boot_time = datetime.utcnow()
            
        if new_state == NexusState.HALTED:
            self._halt_reason = reason
            
        self._current_state = new_state
        self._last_state_change = datetime.utcnow()

    def is_operational(self) -> bool:
        """Determines if the API should accept traffic."""
        return self._current_state in (NexusState.READY, NexusState.DEGRADED)

# Global Access via Singleton
nexus_state_manager = NexusStateManager()
