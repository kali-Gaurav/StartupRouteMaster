"""
Encryption Utils - Task 23: IRCTC Credentials Manager
Provides AES-256 encryption for user IRCTC credentials.
"""

import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# [33.1] AES-GCM Key Management
_SALT = b'\x12\xaf\x88\x99\xc1\xde\xad\xbe\xef' 
_PASS = os.getenv("ENCRYPTION_KEY", "RM_LOCAL_SECRET_KEY").encode()

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=_SALT,
    iterations=100000,
)
_RAW_KEY = kdf.derive(_PASS)
_AESGCM = AESGCM(_RAW_KEY)

def encrypt_data_hardened(plain_text: str) -> tuple:
    """
    [33.2] Authenticated Encryption (AES-GCM).
    Returns (encrypted_base64, iv_base64)
    """
    if not plain_text: return "", ""
    iv = os.urandom(12) # 12 bytes standard for GCM
    ct = _AESGCM.encrypt(iv, plain_text.encode(), None)
    return base64.b64encode(ct).decode(), base64.b64encode(iv).decode()

def decrypt_data_hardened(encrypted_text: str, iv_text: str) -> str:
    """[33.2] Decrypts using IV and ciphertext."""
    if not encrypted_text or not iv_text: return ""
    try:
        ct = base64.b64decode(encrypted_text)
        iv = base64.b64decode(iv_text)
        return _AESGCM.decrypt(iv, ct, None).decode()
    except Exception as e:
        logger.error(f"GCM Decryption failed: {e}")
        return "DECRYPTION_ERROR"

# Legacy support for old Fernet logic (Task 23 compatibility)
from cryptography.fernet import Fernet
_FERNET_KEY = base64.urlsafe_b64encode(_RAW_KEY)
_FERNET = Fernet(_FERNET_KEY)

def encrypt_data(plain_text: str) -> str:
    if not plain_text: return ""
    return _FERNET.encrypt(plain_text.encode()).decode()

def decrypt_data(encrypted_text: str) -> str:
    if not encrypted_text: return ""
    try:
        return _FERNET.decrypt(encrypted_text.encode()).decode()
    except: return "DECRYPTION_ERROR"
