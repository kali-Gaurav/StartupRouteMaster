import re
from typing import Optional, Dict, Any

# Regex Patterns for Instant Intent Recognition
PATTERNS = {
    'pnr': r'(?i)(?:pnr|number|#)?\s*[:=\-]?\s*\b(\d{3}[\-\s]?\d{7}|\d{10})\b', # Matches 10-digit PNR with optional noise
    'search': r'(?i)(?:from\s+)?([A-Z]{2,5}|[a-zA-Z\s]{4,})?\s*(?:to|->|—)\s+([A-Z]{2,5}|[a-zA-Z\s]{4,})', # Matches "NDLS to BCT" or "new delhi to bombai" or "to BCT"
    'sos': r'(?i)\b(sos|emergency|help me|save me|danger|heart attack|mujhe help chahiye|bachao|chot lagi hai)\b',
    'help': r'(?i)\b(help|commands|what can you do|guide)\b',
    'greet': r'(?i)\b(hi|hello|hey|hola|namaste)\b',
    'bookings': r'(?i)\b(bookings|my tickets|history|last ticket|booked)\b',
    'dashboard': r'(?i)\b(dashboard|stats|analytics|my profile)\b',
    'telegram': r'(?i)\b(telegram|bot|link telegram|connect telegram)\b',
    'cancel': r'(?i)\b(cancel|refund|withdraw|refund status)\b',
    'fare': r'(?i)\b(fare|price|cost|ticket rate|kitne ka hai)\b',
    'track': r'(?i)\b(track|live status|where is|kahan pahunchi|running status)\b',
    'station': r'(?i)\b(station|platform|facility|amenity|kahan hai station)\b'
}

def get_local_intent(message: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes message for common intents using high-speed regex.
    Returns a dict with 'intent' and 'entities' if found, else None.
    """
    msg = message.lower()
    # 1. Check SOS (Highest Priority)
    if re.search(PATTERNS['sos'], msg):
        return {"intent": "sos", "confidence": 1.0}

    # 2. Check High-Frequency Controls
    if re.search(PATTERNS['bookings'], msg):
        return {"intent": "bookings", "confidence": 1.0}
    if re.search(PATTERNS['dashboard'], msg):
        return {"intent": "dashboard", "confidence": 1.0}
    if re.search(PATTERNS['telegram'], msg):
        return {"intent": "telegram", "confidence": 1.0}
    if re.search(PATTERNS['cancel'], msg):
        return {"intent": "cancel", "confidence": 1.0}
    if re.search(PATTERNS['fare'], msg):
        return {"intent": "fare", "confidence": 1.0}
    if re.search(PATTERNS['station'], msg):
        return {"intent": "station", "confidence": 1.0}
    if re.search(PATTERNS['track'], msg):
        return {"intent": "track", "confidence": 1.0}

    # 3. Check PNR
    pnr_match = re.search(PATTERNS['pnr'], msg)
    if pnr_match:
        # Clean PNR
        pnr_clean = re.sub(r'[\-\s]', '', pnr_match.group(1))
        return {
            "intent": "pnr", 
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
