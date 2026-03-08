"""
Encryption Utils - Task 23: IRCTC Credentials Manager
Provides AES-256 encryption for user IRCTC credentials.
"""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# [23.3] Master Key Management
# In production, use a dedicated ENCRYPTION_KEY environment variable.
# For local dev, we generate a stable key based on a salt.
_SALT = b'\x12\xaf\x88\x99\xc1\xde\xad\xbe\xef' # Stable salt for local
_PASS = os.getenv("ENCRYPTION_KEY", "RM_LOCAL_SECRET_KEY").encode()

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=_SALT,
    iterations=100000,
)
_KEY = base64.urlsafe_b64encode(kdf.derive(_PASS))
_FERNET = Fernet(_KEY)

def encrypt_data(plain_text: str) -> str:
    """[23.2] Encrypts a string and returns a base64 encoded string."""
    if not plain_text: return ""
    return _FERNET.encrypt(plain_text.encode()).decode()

def decrypt_data(encrypted_text: str) -> str:
    """[23.2] Decrypts a base64 encoded string back to plain text."""
    if not encrypted_text: return ""
    try:
        return _FERNET.decrypt(encrypted_text.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return "DECRYPTION_ERROR"
