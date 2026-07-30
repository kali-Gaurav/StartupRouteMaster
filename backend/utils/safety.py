import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SafetyScanner:
    """
    Scans user input for prompt injection attempts and prohibited content.
    """
    
    # Common Jailbreak patterns
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+all\s+previous",
        r"(?i)disregard\s+all\s+instructions",
        r"(?i)you\s+are\s+now\s+a\s+different\s+ai",
        r"(?i)system\s+override",
        r"(?i)new\s+rule:",
        r"(?i)dan\s+mode",
        r"(?i)act\s+as\s+a\s+developer",
    ]
    
    # Prohibited railway-adjacent sensitive topics
    BLACKLIST = [
        r"(?i)hack\s+irctc",
        r"(?i)fake\s+ticket",
        r"(?i)bypass\s+payment",
        r"(?i)credit\s+card\s+details",
        r"(?i)root\s+access",
    ]

    @staticmethod
    def is_safe(message: str) -> bool:
        """
        Returns False if a security risk is detected.
        """
        # 1. Check Injection Patterns
        for pattern in SafetyScanner.INJECTION_PATTERNS:
            if re.search(pattern, message):
                logger.warning(f"SECURITY ALERT: Prompt Injection detected: {pattern}")
                return False
                
        # 2. Check Blacklisted Content
        for pattern in SafetyScanner.BLACKLIST:
            if re.search(pattern, message):
                logger.warning(f"SECURITY ALERT: Prohibited content attempt: {pattern}")
                return False
                
        # 3. Check for unusual characters (Basic)
        if message.count('{') > 5 or message.count('[') > 5:
            return False
            
        return True
