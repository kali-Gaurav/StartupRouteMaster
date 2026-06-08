import hashlib
import logging
import hmac
from typing import Optional
from core.nexus.security.fingerprint import nexus_fp

from core.nexus.audit.chaos import chaos_trap

logger = logging.getLogger("nexus.financial.signer")

class LedgerSigner:
    """[Task 4.6] Financial Cryptography. Signs ledger entries using Nexus Fingerprints."""
    
    def __init__(self):
        self._secret: Optional[str] = None
        
    async def _get_secret(self) -> str:
        """Retrieve the signing secret from protected storage."""
        if not self._secret:
             # Try to get existing key, or generate a baseline for this VPS
             key = await nexus_fp.get_key("ledger_signing_v3")
             if not key:
                  # Generate a new 256-bit signing secret
                  import secrets
                  key = secrets.token_hex(32)
                  await nexus_fp.store_key("ledger_signing_v3", key)
                  logger.warning("🔑 [NEXUS:SIGNER] New Ledger Signing Secret Generated and Isolated.")
             self._secret = key
        return self._secret

    @chaos_trap("financial_signing")
    async def generate_signature(self, entry_id: int, data_string: str) -> str:
        """Create a HMAC-SHA256 signature for a ledger entry."""
        secret = await self._get_secret()
        payload = f"{entry_id}:{data_string}".encode()
        
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return signature

    async def verify_signature(self, entry_id: int, data_string: str, signature: str) -> bool:
        """Confirm a signature matches the entry data."""
        expected = await self.generate_signature(entry_id, data_string)
        return hmac.compare_digest(expected, signature)

ledger_signer = LedgerSigner()
