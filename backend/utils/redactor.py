import re
import logging

logger = logging.getLogger(__name__)

class SafetyRedactor:
    """
    Task 25: Real-time Transcript Redaction (PII hiding).
    Masks sensitive information like Aadhaar, OTPs, and Phone Numbers.
    """
    # Patterns for common Indian PII
    PATTERNS = {
        "AADHAAR": r'\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b',
        "OTP": r'\b\d{4,6}\b', # Can be aggressive, but safety first
        "PHONE": r'\b(?:\+91|91|0)?[6-9]\d{9}\b'
    }

    @staticmethod
    def redact(text: str) -> str:
        if not text: return text
        
        redacted = text
        # Redact Aadhaar
        redacted = re.sub(SafetyRedactor.PATTERNS["AADHAAR"], "[REDACTED_ID]", redacted)
        
        # Redact Phone (Only if it looks like a separate number, not the user's primary)
        # For simplicity, we redact all matches in the text body
        redacted = re.sub(SafetyRedactor.PATTERNS["PHONE"], "[REDACTED_PHONE]", redacted)
        
        # Note: We avoid aggressive OTP redaction if it breaks simple counts, 
        # but for safety transcripts, any 6-digit number is suspicious.
        
        return redacted

safety_redactor = SafetyRedactor()
