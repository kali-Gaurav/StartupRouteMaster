import hashlib
import hmac
import os
from typing import Optional
from fastapi import Request

AUTH_SECRET = os.getenv("AUTH_ENCRYPTION_SECRET", "default_secret_32_chars_long_123456")

def generate_fingerprint(client_id: str, user_agent: str, ip: str) -> str:
    """
    [Task 106] Generate a unique device fingerprint hash.
    Uses IP prefix (/24 for IPv4) to allow minor roaming within the same network.
    """
    # IP Prefixing for resilience
    ip_parts = ip.split('.')
    ip_prefix = ".".join(ip_parts[:3]) if len(ip_parts) == 4 else ip
    
    components = f"{client_id}:{user_agent}:{ip_prefix}"
    return hmac.new(
        AUTH_SECRET.encode(),
        components.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_fingerprint(signature: str, client_id: str, user_agent: str, ip: str) -> bool:
    """Verify if the provided signature matches the dynamic fingerprint."""
    expected = generate_fingerprint(client_id, user_agent, ip)
    return hmac.compare_digest(signature, expected)
