import os
import logging
from typing import Any, Optional
from starlette.responses import JSONResponse

logger = logging.getLogger("api-responses")

class SafeJSONResponse(JSONResponse):
    """
    Standard JSONResponse augmented with resilient CORS headers and 
    Subtask 4.6: Dynamic Retry-After headers for traffic shaping.
    """
    def __init__(self, content: Any, status_code: int = 200, **kwargs):
        headers = kwargs.get("headers", {})
        
        # 1. Resilient CORS injection
        origin = os.getenv("CORS_ALLOWED_ORIGINS", "*")
        if origin == "*":
            headers["Access-Control-Allow-Origin"] = "*"
        else:
            headers["Access-Control-Allow-Origin"] = origin.split(",")[0]
            
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
        headers["Access-Control-Allow-Credentials"] = "true"

        # 2. Subtask 4.6: Adaptive Retry-After for Throttling/Shedding
        if status_code in (429, 503):
            try:
                from core.metrics import jit_metrics, SurgeLevel
                
                # Default retry waits
                retry_map = {
                    SurgeLevel.NORMAL: 5,
                    SurgeLevel.ELEVATED: 15,
                    SurgeLevel.HIGH: 30,
                    SurgeLevel.CRITICAL: 60
                }
                
                current_level = jit_metrics.surge_level
                retry_seconds = retry_map.get(current_level, 10)
                
                # Injected header
                headers["Retry-After"] = str(retry_seconds)
                
                # Also update content if it's a dict to include retry_after for UI
                if isinstance(content, dict):
                    content["retry_after"] = retry_seconds
                    
            except Exception as e:
                # Fail safe: use a static 10s if metrics fail
                headers["Retry-After"] = "10"
        
        kwargs["headers"] = headers
        super().__init__(content, status_code, **kwargs)
