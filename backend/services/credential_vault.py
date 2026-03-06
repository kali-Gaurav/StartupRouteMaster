import logging
import os
import base64
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session
from database.models import User, AuditLog
from config import Config

logger = logging.getLogger(__name__)

class CredentialVault:
    """
    Task 35: AES-256 Credential Vault.
    Handles secure storage and retrieval of IRCTC credentials.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # Task 35.1: Master Key from Config
        self.master_key = Config.RAZORPAY_KEY_SECRET[:32].encode('utf-8').ljust(32, b'\0')

    def _derive_key(self, salt: bytes) -> bytes:
        """Task 35.1: PBKDF2 Key Derivation."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.master_key)

    def store_credentials(self, user_id: str, irctc_user: str, irctc_pass: str, persistent: bool = False):
        """Task 35.9: Encryption at REST."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user: return False

        # Task 35.2: Per-user IV and Salt
        iv = os.urandom(16)
        salt = os.urandom(16)
        
        derived_key = self._derive_key(salt)
        
        # Combine user/pass for encryption
        plaintext = f"{irctc_user}:{irctc_pass}".encode('utf-8')
        # Padding (PKCS7 style manual)
        padding_len = 16 - (len(plaintext) % 16)
        plaintext += bytes([padding_len] * padding_len)
        
        cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Store IV + Salt + Ciphertext
        # We use largebinary columns. Storing salt inside the blob.
        user.creds_iv = iv
        user.encrypted_irctc_creds = salt + ciphertext
        user.opt_in_persistent_creds = persistent
        
        self.db.add(AuditLog(
            entity_type="User", entity_id=user_id, action="VAULT_STORE", 
            performed_by="SYSTEM", reason="Credentials encrypted and stored"
        ))
        self.db.commit()
        return True

    def get_credentials(self, user_id: str) -> Optional[Tuple[str, str]]:
        """Task 35.5: Security Audit Log on access."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.encrypted_irctc_creds:
            return None

        iv = user.creds_iv
        blob = user.encrypted_irctc_creds
        salt = blob[:16]
        ciphertext = blob[16:]
        
        derived_key = self._derive_key(salt)
        
        cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        try:
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            padding_len = padded_plaintext[-1]
            plaintext = padded_plaintext[:-padding_len].decode('utf-8')
            
            # Log the access
            self.db.add(AuditLog(
                entity_type="User", entity_id=user_id, action="VAULT_ACCESS", 
                performed_by="SYSTEM", reason="Credentials decrypted for booking"
            ))
            self.db.commit()
            
            parts = plaintext.split(":", 1)
            return parts[0], parts[1]
        except Exception as e:
            logger.error(f"Vault decryption failed for user {user_id}: {e}")
            return None

    def auto_wipe(self, user_id: str):
        """Task 35.3: Auto-wipe credentials after completion."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and not user.opt_in_persistent_creds:
            user.encrypted_irctc_creds = None
            user.creds_iv = None
            self.db.add(AuditLog(
                entity_type="User", entity_id=user_id, action="VAULT_WIPE", 
                performed_by="SYSTEM", reason="Auto-wipe triggered (Non-persistent)"
            ))
            self.db.commit()
            logger.info(f"Task 35.3: Credentials wiped for user {user_id}")

    def is_weak_password(self, password: str) -> bool:
        """Task 35.7: Weak password detection."""
        if len(password) < 8: return True
        if password.lower() in ["password", "irctc123", "12345678"]: return True
        return False
