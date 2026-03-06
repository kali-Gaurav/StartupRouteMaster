from cryptography.fernet import Fernet
import os
import logging

logger = logging.getLogger(__name__)

class CredentialVault:
    """
    Task 49: AES-256 User Credential Vault.
    Uses a master key from environment variables.
    """
    def __init__(self):
        self.key = os.getenv("MASTER_VAULT_KEY", Fernet.generate_key().decode())
        self.fernet = Fernet(self.key.encode())

    def encrypt(self, plain_text: str) -> str:
        return self.fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

credential_vault = CredentialVault()
