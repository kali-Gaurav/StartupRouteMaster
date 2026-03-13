import re
from typing import Optional, Dict, Any
from rapidfuzz import fuzz, process

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

# Task 2.8: Canonical Keywords for Fuzzy Correction
CANONICAL_INTENTS = {
    "pnr": ["pnr", "pner", "pnrr"],
    "search": ["search", "serch", "find", "finds", "book", "findtrain"],
    "sos": ["sos", "emergency", "help", "soos"],
    "bookings": ["bookings", "history", "boking", "booking", "tickets"],
    "dashboard": ["dashboard", "dashbord", "stats", "analytics"],
    "track": ["track", "trak", "trac", "whereis"],
    "cancel": ["cancel", "refund", "cancle"],
    "fare": ["fare", "price", "cost", "ticketprice"],
    "station": ["station", "platform", "platforms"]
}

def _fuzzy_correct_intent(message: str) -> Optional[str]:
    """Task 2.8: Silent correction of common command typos."""
    # Remove noise before fuzzy checking
    noise = r'\b(please|show|me|my|get|check|give|view|open)\b'
    clean_msg = re.sub(noise, '', message.lower()).strip()
    words = clean_msg.split()
    if not words: return None
    
    # Check first 2 words for command triggers
    for word in words[:2]:
        if len(word) < 3: continue
        
        for intent, keywords in CANONICAL_INTENTS.items():
            if word in keywords: return intent
            
            match = process.extractOne(word, keywords, scorer=fuzz.ratio)
            if match and match[1] > 80: # Slightly lower threshold for cleaned words
                return intent
                
    return None

def get_local_intent(message: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes message for common intents using high-speed regex.
    Returns a dict with 'intent' and 'entities' if found, else None.
    """
    msg = message.lower().strip()
    
    # 1. Task 2.8: Try Fuzzy Correction on the command word
    corrected_intent = _fuzzy_correct_intent(msg)
    
    # 2. Check SOS (Highest Priority)
    if corrected_intent == "sos" or re.search(PATTERNS['sos'], msg):
        return {"intent": "sos", "confidence": 1.0}

    # 3. Check High-Frequency Controls
    if corrected_intent == "bookings" or re.search(PATTERNS['bookings'], msg):
        return {"intent": "bookings", "confidence": 1.0}
    if corrected_intent == "dashboard" or re.search(PATTERNS['dashboard'], msg):
        return {"intent": "dashboard", "confidence": 1.0}
    if corrected_intent == "telegram" or re.search(PATTERNS['telegram'], msg):
        return {"intent": "telegram", "confidence": 1.0}
    if corrected_intent == "cancel" or re.search(PATTERNS['cancel'], msg):
        return {"intent": "cancel", "confidence": 1.0}
    if corrected_intent == "fare" or re.search(PATTERNS['fare'], msg):
        return {"intent": "fare", "confidence": 1.0}
    if corrected_intent == "station" or re.search(PATTERNS['station'], msg):
        return {"intent": "station", "confidence": 1.0}
    if corrected_intent == "track" or re.search(PATTERNS['track'], msg):
        return {"intent": "track", "confidence": 1.0}

    # 4. Check PNR
    pnr_match = re.search(PATTERNS['pnr'], msg)
    if corrected_intent == "pnr" or pnr_match:
        # Clean PNR
        pnr_clean = re.sub(r'[\-\s]', '', pnr_match.group(1)) if pnr_match else None
        return {
            "intent": "pnr", 
            "entities": {"pnr": pnr_clean} if pnr_clean else {},
            "confidence": 1.0
        }

    # 5. Check Search (Source to Destination)
    search_match = re.search(PATTERNS['search'], message)
    if corrected_intent == "search" or search_match:
        return {
            "intent": "search",
            "entities": {
                "source": search_match.group(1).upper().strip() if (search_match and search_match.group(1)) else None,
                "destination": search_match.group(2).upper().strip() if (search_match and search_match.group(2)) else None
            },
            "confidence": 0.95
        }

    # 6. Check Greet
    if corrected_intent == "greet" or re.search(PATTERNS['greet'], message):
        return {"intent": "greet", "confidence": 1.0}

    # 7. Check Help
    if corrected_intent == "help" or re.search(PATTERNS['help'], message):
        return {"intent": "help", "confidence": 1.0}

    return None
