import logging
import os
import base64
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from collections import deque
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from sqlalchemy.orm import Session
from database.models import User, AuditLog
from config import Config
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger(__name__)


class CredentialVaultMetrics:
    """Metrics tracking for credential vault service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=500)
        self._metrics_lock = asyncio.Lock()
        self._access_counts: Dict[str, int] = {}
    
    async def record_access(self, operation: str, success: bool, duration_ms: float):
        """Record credential access metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms
            })
            self._access_counts[operation] = self._access_counts.get(operation, 0) + 1
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        durations = [m["duration_ms"] for m in self._metrics]
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
            "operation_counts": self._access_counts.copy()
        }


class CredentialVault:
    """
    Task 35: AES-256 Credential Vault.
    Handles secure storage and retrieval of IRCTC credentials.
    
    Enhanced with resilience patterns: circuit breakers, retry policies, and metrics tracking.
    """
    
        self.db = db
        # Security Fix: Use dedicated Vault Key instead of reusing Razorpay secret
        master_key_str = os.getenv("VAULT_ENCRYPTION_KEY")
        if not master_key_str:
            import secrets
            logger.critical("CRITICAL: VAULT_ENCRYPTION_KEY missing! Using ephemeral key. Vault data will be unrecoverable on restart.")
            master_key_str = secrets.token_hex(32)
        self.master_key = master_key_str[:32].encode('utf-8').ljust(32, b'\0')
        
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "credential_vault_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        
        # Retry policy for database operations
        self._db_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "connection" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics = CredentialVaultMetrics()
        
        logger.info("CredentialVault initialized with resilience patterns")

    def _derive_key(self, salt: bytes) -> bytes:
        """Task 35.1: PBKDF2 Key Derivation."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
            backend=default_backend()
        )
        return kdf.derive(self.master_key)

    async def store_credentials(self, user_id: str, irctc_user: str, irctc_pass: str, persistent: bool = False):
        """Task 35.9: Encryption at REST with circuit breaker protection."""
        import time
        
        async def _do_store():
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user: 
                return False

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
            user.creds_iv = iv  # type: ignore
            user.encrypted_irctc_creds = salt + ciphertext  # type: ignore
            user.opt_in_persistent_creds = persistent  # type: ignore
            
            self.db.add(AuditLog(
                entity_type="User", entity_id=user_id, action="VAULT_STORE", 
                performed_by="SYSTEM", reason="Credentials encrypted and stored"
            ))
            self.db.commit()
            return True
        
        start_time = time.perf_counter()
        try:
            result = await self._db_breaker.execute(
                self._db_retry.execute,
                _do_store
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            asyncio.create_task(self._metrics.record_access("store", bool(result), duration_ms))
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            asyncio.create_task(self._metrics.record_access("store", False, duration_ms))
            logger.error(f"Failed to store credentials: {e}")
            return False

    async def get_credentials(self, user_id: str) -> Optional[Tuple[str, str]]:
        """Task 35.5: Security Audit Log on access with circuit breaker protection."""
        import time
        
        async def _do_get():
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or user.encrypted_irctc_creds is None:
                return None

            iv = user.creds_iv  # type: ignore
            blob = user.encrypted_irctc_creds  # type: ignore
            salt = blob[:16]
            ciphertext = blob[16:]
            
            derived_key = self._derive_key(salt)  # type: ignore
            
            cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv), backend=default_backend())  # type: ignore
            decryptor = cipher.decryptor()
            
            try:
                padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()  # type: ignore
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
        
        start_time = time.perf_counter()
        try:
            result = await self._db_breaker.execute(
                self._db_retry.execute,
                _do_get
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            asyncio.create_task(self._metrics.record_access("get", result is not None, duration_ms))
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            asyncio.create_task(self._metrics.record_access("get", False, duration_ms))
            logger.error(f"Failed to get credentials: {e}")
            return None

    def auto_wipe(self, user_id: str):
        """Task 35.3: Auto-wipe credentials after completion."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and not user.opt_in_persistent_creds:  # type: ignore
            user.encrypted_irctc_creds = None  # type: ignore
            user.creds_iv = None  # type: ignore
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
# =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": self._db_breaker.get_metrics().to_dict(),
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for credential_vault")
