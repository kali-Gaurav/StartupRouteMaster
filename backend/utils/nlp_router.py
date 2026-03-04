import re
from typing import Optional, Dict, Any

# Regex Patterns for Instant Intent Recognition
PATTERNS = {
    'pnr': r'\b\d{10}\b', # Matches 10-digit PNR
    'search': r'(?i)\b([A-Z]{2,5})\s+(?:to|->|—)\s+([A-Z]{2,5})\b', # Matches "NDLS to BCT"
    'sos': r'(?i)\b(sos|emergency|help me|save me)\b',
    'help': r'(?i)\b(help|commands|what can you do|guide)\b',
    'greet': r'(?i)\b(hi|hello|hey|hola|namaste)\b'
}

def get_local_intent(message: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes message for common intents using high-speed regex.
    Returns a dict with 'intent' and 'entities' if found, else None.
    """
    # 1. Check SOS (Highest Priority)
    if re.search(PATTERNS['sos'], message):
        return {"intent": "sos", "confidence": 1.0}

    # 2. Check PNR
    pnr_match = re.search(PATTERNS['pnr'], message)
    if pnr_match:
        return {
            "intent": "pnr_status", 
            "entities": {"pnr": pnr_match.group(0)},
            "confidence": 1.0
        }

    # 3. Check Search (Source to Destination)
    search_match = re.search(PATTERNS['search'], message)
    if search_match:
        return {
            "intent": "search",
            "entities": {
                "source": search_match.group(1).upper(),
                "destination": search_match.group(2).upper()
            },
            "confidence": 0.95
        }

    # 4. Check Greet
    if re.search(PATTERNS['greet'], message):
        return {"intent": "greet", "confidence": 1.0}

    # 5. Check Help
    if re.search(PATTERNS['help'], message):
        return {"intent": "help", "confidence": 1.0}

    return None
