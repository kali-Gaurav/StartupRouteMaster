from enum import Enum

class SystemState(Enum):
    """[Task 1.1] Operational State Machine for RouteMaster V3 Nexus Fiber."""
    OFFLINE = "OFFLINE"       # System is halted or starting up
    BOOTING = "BOOTING"       # Dependency graph being resolved
    READY = "READY"           # All mission-critical nodes online
    DEGRADED = "DEGRADED"     # System running with failing non-critical nodes
    SAFE_MODE = "SAFE_MODE"   # Critical failure: Only health/admin routes active
    HALTED = "HALTED"         # Graceful shutdown in progress or complete
