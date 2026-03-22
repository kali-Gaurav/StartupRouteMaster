import os
import orjson
from typing import Any
from starlette.responses import JSONResponse

class SafeJSONResponse(JSONResponse):
    """
    Task 25: Optimized High-Performance Response.
    1. Uses orjson for 5-10x faster serialization.
    2. Automatically prunes null values to save bandwidth on VPS.
    3. Resilient CORS injection.
    """
    def render(self, content: Any) -> bytes:
        # Pruning: Remove None values from dicts to save bytes
        if isinstance(content, dict):
            content = {k: v for k, v in content.items() if v is not None}
            
        return orjson.dumps(
            content, 
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME
        )

    def __init__(self, content: Any, status_code: int = 200, **kwargs):
        headers = kwargs.get("headers", {})
        
        # Minify internal headers
        if "X-Request-ID" in headers:
            headers["X-RID"] = headers.pop("X-Request-ID")
            
        # Resilient CORS injection
        origin = os.getenv("CORS_ALLOWED_ORIGINS", "*")
        if origin == "*":
            headers["Access-Control-Allow-Origin"] = "*"
        else:
            headers["Access-Control-Allow-Origin"] = origin.split(",")[0]
            
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
        headers["Access-Control-Allow-Credentials"] = "true"
        # Hide server info
        headers["Server"] = "RouteMaster-Resilient"
        
        kwargs["headers"] = headers
        super().__init__(content, status_code, **kwargs)
