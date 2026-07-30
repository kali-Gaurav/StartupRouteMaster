import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import secrets
import logging

logger = logging.getLogger(__name__)

# Security Fix: Require environment variable, fallback to ephemeral key with critical warning
SECRET_KEY = os.getenv("PII_ENCRYPTION_KEY")
if not SECRET_KEY:
    logger.critical("CRITICAL: PII_ENCRYPTION_KEY missing! Using ephemeral random key. Data will be lost on restart!")
    SECRET_KEY = secrets.token_hex(32)

def _get_fernet():
    salt_env = os.getenv("PII_SALT")
    salt = salt_env.encode() if salt_env else b"railway-static-salt"
    
    # Derive a stable key from the SECRET_KEY using OWASP recommended iterations
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))
    return Fernet(key)

def encrypt_pii(data: str) -> str:
    if not data: return data
    f = _get_fernet()
    return f.encrypt(data.encode()).decode()

def decrypt_pii(token: str) -> str:
    if not token: return token
    try:
        f = _get_fernet()
        return f.decrypt(token.encode()).decode()
    except:
        return "[DECRYPTION_ERROR]"
