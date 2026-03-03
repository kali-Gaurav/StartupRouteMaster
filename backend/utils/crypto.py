import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# In production, this should be in .env
SECRET_KEY = os.getenv("PII_ENCRYPTION_KEY", "prod-secret-key-for-pii-encryption-123")

def _get_fernet():
    # Derive a stable key from the SECRET_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"railway-static-salt",
        iterations=100000,
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
