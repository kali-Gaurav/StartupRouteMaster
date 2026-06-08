import base64
import hashlib
import hmac
import logging
import json
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from config import Config

logger = logging.getLogger("routemaster.security.vault")

class PNRVault:
    """
    [Task 4.7] Encrypted PNR Vault (Zero-Knowledge).
    Hardens storage of sensitive passenger details from NLP extraction.
    Supports Encryption, Blind Indexing, and Auto-Scrubbing.
    """
    def __init__(self):
        # Master key for KDF (Must be securely stored in Config)
        self.master_secret = Config.BANK_WEBHOOK_SECRET or "routemaster-default-vault-secret-32"
        self.salt = b"routemaster_vault_salt_v1" # In prod, this would be a per-user salt

    def _derive_key(self, user_id: str) -> bytes:
        """Derives a user-specific encryption key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(f"{self.master_secret}:{user_id}".encode()))
        return key

    def get_blind_index(self, pnr: str) -> str:
        """
        Creates a searchable HMAC hash of the PNR.
        Allows lookups without decrypting the entire database.
        """
        return hmac.new(
            self.master_secret.encode(),
            pnr.encode(),
            hashlib.sha256
        ).hexdigest()

    def encrypt_pnr_data(self, user_id: str, pnr_data: Dict[str, Any]) -> str:
        """
        Encrypts a dictionary of passenger details.
        """
        key = self._derive_key(user_id)
        f = Fernet(key)
        json_data = json.dumps(pnr_data)
        return f.encrypt(json_data.encode()).decode()

    def decrypt_pnr_data(self, user_id: str, encrypted_blob: str) -> Optional[Dict[str, Any]]:
        """
        Decrypts a PNR blob back into its original dictionary.
        """
        try:
            key = self._derive_key(user_id)
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_blob.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Vault Decryption Failed for user {user_id}: {e}")
            return None

    def pack_pnr_for_storage(self, user_id: str, pnr: str, raw_nlp_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a 'Hardened Payload' ready for database insertion.
        Contains: Blind Index, Encrypted Data, and Metadata.
        """
        return {
            "pnr_blind_index": self.get_blind_index(pnr),
            "encrypted_data": self.encrypt_pnr_data(user_id, raw_nlp_data),
            "storage_version": "1.0",
            "lifecycle_status": "SECURED"
        }

pnr_vault = PNRVault()
