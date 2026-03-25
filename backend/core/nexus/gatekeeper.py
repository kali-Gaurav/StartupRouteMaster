from fastapi import HTTPException, status, Response
from core.nexus.state import nexus_state_manager, NexusState

logger = logging.getLogger("nexus.gatekeeper")

async def nexus_gatekeeper(response: Response):
    """
    [Task 4 / 8] High-Integrity FastAPI Dependency.
    1. Prevents traffic if engine isn't READY.
    2. Injects V3 Operational Branding (X-Nexus-State) into response.
    """
    state = nexus_state_manager.current_state
    
    # Task 8: Inbound Branding for all V3 requests
    response.headers["X-Nexus-State"] = state.value
    response.headers["X-Nexus-Version"] = "3.1.0-Fiber"
    
    if state == NexusState.OFFLINE or state == NexusState.BOOTING:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Nexus Engine Is Booting",
                "status": state.value,
                "msg": "RouteMaster V3 is initializing core dependencies."
            }
        )
        
    if state == NexusState.HALTED:
        logger.critical(f"🚨 [GATEKEEPER] Request rejected due to HALTED state: {nexus_state_manager._halt_reason}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Nexus Engine Halted",
                "status": state.value,
                "reason": nexus_state_manager._halt_reason,
                "msg": "Platform integrity compromised. Manual intervention required."
            }
        )
        
    # READY and DEGRADED states are operational
    return True

class NexusStatusMonitor:
    """[Task 4.1] Continuously audits the health of all registered nodes."""
    
    def __init__(self, bootstrapper):
        self._boot = bootstrapper
        
    def get_full_health(self):
        """Returns the real-time status of the 'Nexus Fiber' ecosystem."""
        return {
            "system_state": nexus_state_manager.current_state.value,
            "is_operational": nexus_state_manager.is_operational(),
            "nodes": {
                name: {
                    "healthy": node.is_healthy,
                    "last_error": node.last_error,
                    "uptime": str(datetime.utcnow() - node._start_time) if node._start_time else None
                }
                for name, node in self._boot._nodes.items()
            }
        }
