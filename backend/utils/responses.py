import os
from typing import Any
from starlette.responses import JSONResponse

class SafeJSONResponse(JSONResponse):
    """
    Standard JSONResponse augmented with resilient CORS headers.
    Ensures that even on middleware crashes (500/503), the frontend
    can read the error payload.
    """
    def __init__(self, content: Any, status_code: int = 200, **kwargs):
        headers = kwargs.get("headers", {})
        
        # Resilient CORS injection
        origin = os.getenv("CORS_ALLOWED_ORIGINS", "*")
        if origin == "*":
            headers["Access-Control-Allow-Origin"] = "*"
        else:
            # For multi-origin, we'd need the request object to match, 
            # but for safety we use the first one or '*' if needed.
            headers["Access-Control-Allow-Origin"] = origin.split(",")[0]
            
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
        headers["Access-Control-Allow-Credentials"] = "true"
        
        kwargs["headers"] = headers
        super().__init__(content, status_code, **kwargs)
