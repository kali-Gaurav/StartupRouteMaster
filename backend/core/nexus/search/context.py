from fastapi import Request
from typing import Any, Optional

class NexusRequestContext:
    """[Task 17] Formal Request Metadata/Context Handler."""
    
    @staticmethod
    def initialize(request: Request, source: str = None, destination: str = None):
        request.state.source = source
        request.state.destination = destination
        request.state.start_ts = getattr(request.state, "start_ts", None)
        request.state.trace_id = getattr(request.api_state, "trace_id", "nexus-v3-fiber")
        
    @staticmethod
    def get_audit_payload(request: Request, **extra) -> dict:
        """Returns a snapshot of the request for logging/audit."""
        return {
            "source": getattr(request.state, "source", "UNKNOWN"),
            "destination": getattr(request.state, "destination", "UNKNOWN"),
            "geo_state": getattr(request.state, "geo_state", "UNKNOWN"),
            "trace_id": getattr(request.state, "nexus_id", "UNKNOWN"),
            **extra
        }

nexus_ctx = NexusRequestContext()
