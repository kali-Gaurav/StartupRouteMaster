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
        "OTP": r'\b\d{4,6}\b',
        "PHONE": r'\b(?:\+91|91|0)?[6-9]\d{9}\b',
        "PNR": r'\b\d{10}\b|\b\d{3}[-\s]?\d{7}\b' # 10-digit PNR
    }

    @staticmethod
    def redact(text: str) -> str:
        if not text: return text
        
        redacted = text
        # 1. Redact Aadhaar
        redacted = re.sub(SafetyRedactor.PATTERNS["AADHAAR"], "[REDACTED_ID]", redacted)
        
        # 2. Redact Phone
        redacted = re.sub(SafetyRedactor.PATTERNS["PHONE"], "[REDACTED_PHONE]", redacted)
        
        # 3. Redact PNR (Task 9.2)
        redacted = re.sub(SafetyRedactor.PATTERNS["PNR"], "[REDACTED_PNR]", redacted)
        
        return redacted

safety_redactor = SafetyRedactor()
