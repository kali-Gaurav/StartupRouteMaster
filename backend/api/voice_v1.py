import logging
from fastapi import APIRouter, Depends
from typing import Dict, Any
from services.search_service import SearchService
from database.session import SessionTransit

logger = logging.getLogger("routemaster.api.voice")
router = APIRouter(prefix="/v1/voice", tags=["AI"])

class VoiceIntentParser:
    """
    [P16] Conversational AI Gateway.
    Parses natural language queries into RouteMaster search parameters.
    """
    
    @staticmethod
    def parse_text(query: str) -> Dict[str, Any]:
        """
        Extracts Source, Destination, and Date from speech strings.
        Example: "Next train from Delhi to Agra"
        """
        query = query.lower()
        words = query.split()
        # Temporal detection
        travel_date = "today"
        if "tomorrow" in query:
            travel_date = "tomorrow"
        elif "next week" in query:
            travel_date = "next_week"

        # Heuristic for "from X to Y"
        try:
            # Handle "X to Y" or "from X to Y"
            if "from" in words and "to" in words:
                from_idx = words.index("from")
                to_idx = words.index("to")
                src = words[from_idx + 1].upper()
                dst = words[to_idx + 1].upper()
            elif "to" in words:
                to_idx = words.index("to")
                src = words[to_idx - 1].upper()
                dst = words[to_idx + 1].upper()
            else:
                return {"intent": "UNKNOWN", "original": query}
                
            return {
                "source": src, 
                "destination": dst, 
                "date": travel_date,
                "intent": "SEARCH"
            }
        except:
            return {"intent": "UNKNOWN", "original": query}

@router.get("/parse")
async def process_voice_query(q: str):
    """
    [P16] Endpoint for voice-to-route conversion.
    """
    intent = VoiceIntentParser.parse_text(q)
    
    if intent["intent"] == "SEARCH":
        logger.info(f"🎙️ [VOICE] Intent Detected: {intent['source']} -> {intent['destination']}")
        # In a real app, this would redirect or return the search results immediately
        return {
            "action": "EXECUTE_SEARCH",
            "params": intent,
            "speech_response": f"Searching for the next journeys from {intent['source']} to {intent['destination']}"
        }
    
    return {"action": "CLARIFY", "speech_response": "I didn't catch that. Try saying 'From Delhi to Mumbai'."}
