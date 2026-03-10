import re
from typing import Optional, Dict, Any

# Regex Patterns for Instant Intent Recognition
PATTERNS = {
    'pnr': r'(?i)(?:pnr|number|#)?\s*[:=\-]?\s*\b(\d{3}[\-\s]?\d{7}|\d{10})\b', # Matches 10-digit PNR with optional noise
    'search': r'(?i)(?:from\s+)?([A-Z]{2,5}|[a-zA-Z\s]{4,})?\s*(?:to|->|—)\s+([A-Z]{2,5}|[a-zA-Z\s]{4,})', # Matches "NDLS to BCT" or "new delhi to bombai" or "to BCT"
    'sos': r'(?i)\b(sos|emergency|help me|save me|danger|heart attack|mujhe help chahiye|bachao|chot lagi hai)\b',
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
        # Clean PNR
        pnr_clean = re.sub(r'[\-\s]', '', pnr_match.group(1))
        return {
            "intent": "pnr_status", 
            "entities": {"pnr": pnr_clean},
            "confidence": 1.0
        }

    # 3. Check Search (Source to Destination)
    search_match = re.search(PATTERNS['search'], message)
    if search_match:
        return {
            "intent": "search",
            "entities": {
                "source": search_match.group(1).upper().strip(),
                "destination": search_match.group(2).upper().strip()
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
