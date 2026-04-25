import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("routemaster.localization")

class GeoAdaptiveLocalizationMiddleware(BaseHTTPMiddleware):
    """
    [P15] Cultural Intelligence.
    Detects the user's preferred language based on search context or Geo-IP.
    """
    
    # Mapping of region prefixes to languages
    # e.g. searches starting in Tamil Nadu default to Tamil
    REGION_MAP = {
        "MAS": "ta", # Chennai -> Tamil
        "SBC": "kn", # Bangalore -> Kannada
        "NDLS": "hi", # Delhi -> Hindi
        "HWH": "bn", # Howrah -> Bengali
        "CSTM": "mr" # Mumbai -> Marathi
    }

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        
        # Check if we have a search context (from query params)
        src = request.query_params.get("source") or request.query_params.get("src")
        
        target_lang = "en" # Default to English
        
        if src:
            # Check for region prefix matches
            for hub, lang in self.REGION_MAP.items():
                if src.startswith(hub):
                    target_lang = lang
                    break
        
        # Inject the predicted language into the response header for the frontend to pick up
        response.headers["X-RouteMaster-Predicted-Locale"] = target_lang
        
        if target_lang != "en":
             logger.debug(f"🌍 [LOCALE] Auto-adapting search context for {src} to {target_lang}")
             
        return response
