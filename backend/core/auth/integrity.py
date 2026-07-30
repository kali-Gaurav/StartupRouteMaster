import hmac
import hashlib
import json
from datetime import datetime
import os
from typing import Any, Dict, Optional

# [Industrial Rigor] Secret key for signing search results to prevent client-side manipulation.
# In production, this must be fetched from a secure Secret Manager (e.g., Vault or AWS Secrets Manager).
INTEGRITY_SECRET = os.getenv("GATEWAY_INTEGRITY_SECRET", "industrial_default_secret_99")

def sign_result_payload(data: Any, user_id: str, nonce: str, ts: Optional[int] = None) -> str:
    """
    [SENTINEL S2] Cryptographic integrity signing.
    Ensures the response payload wasn't tampered with and belongs to the original requester.
    """
    secret = os.getenv("GATEWAY_INTEGRITY_SECRET", "industrial_default_secret_99")
    
    # Contextual binding
    # We only sign the 'data' part of the response
    payload = {
        "data": data,
        "user_id": user_id,
        "nonce": nonce,
        "ts": ts or int(datetime.utcnow().timestamp())
    }
    
    serialized = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode(), serialized.encode(), hashlib.sha256).hexdigest()

def verify_result_integrity(data: Dict, signature: str, user_id: str, nonce: str, ts: int) -> bool:
    """
    Client-side or verification-side validation.
    """
    if not signature or not nonce or not ts:
        return False
        
    expected = sign_result_payload(data, user_id, nonce, ts)
    return hmac.compare_digest(expected, signature)
