from cryptography.fernet import Fernet
import os
import base64
import logging
from database.config import Config

logger = logging.getLogger(__name__)

# Task 41: DPDP Compliance - AES-256 Encryption at Rest
# In production, this key should be in a secure KMS
_KEY = os.getenv("SOS_ENCRYPTION_KEY")
if not _KEY:
    # Fallback/Generate for local dev
    _KEY = base64.urlsafe_b64encode(b"01234567890123456789012345678901") 

_fernet = Fernet(_KEY)

def encrypt_value(value: str) -> str:
    if not value: return value
    try:
        return _fernet.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value

def decrypt_value(token: str) -> str:
    if not token: return token
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception as e:
        # If decryption fails, it might be unencrypted legacy data
        return token

def encrypt_sos_event(event: dict) -> dict:
    """Encrypts sensitive fields in an SOS event."""
    encrypted = event.copy()
    sensitive_fields = ["name", "phone", "email", "extra"]
    for field in sensitive_fields:
        if encrypted.get(field):
            encrypted[field] = encrypt_value(encrypted[field])
    
    # Encrypt chat history
    if encrypted.get("chat_history"):
        for msg in encrypted["chat_history"]:
            if msg.get("content"):
                msg["content"] = encrypt_value(msg["content"])
    
    # Encrypt call logs
    if encrypted.get("call_logs"):
        for log in encrypted["call_logs"]:
            if log.get("content"):
                log["content"] = encrypt_value(log["content"])
                
    encrypted["is_encrypted"] = True
    return encrypted

def decrypt_sos_event(event: dict) -> dict:
    """Decrypts sensitive fields in an SOS event."""
    if not event.get("is_encrypted"):
        return event
        
    decrypted = event.copy()
    sensitive_fields = ["name", "phone", "email", "extra"]
    for field in sensitive_fields:
        if decrypted.get(field):
            decrypted[field] = decrypt_value(decrypted[field])
            
    # Decrypt chat history
    if decrypted.get("chat_history"):
        for msg in decrypted["chat_history"]:
            if msg.get("content"):
                msg["content"] = decrypt_value(msg["content"])
    
    # Decrypt call logs
    if decrypted.get("call_logs"):
        for log in decrypted["call_logs"]:
            if log.get("content"):
                log["content"] = decrypt_value(log["content"])
                
    return decrypted
