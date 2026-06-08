"""
TLS Configuration for the Contextual Availability Transformer (CAT) system.
Provides secure HTTPS configuration and certificate management.
"""

import ssl
import logging
from typing import Optional, Tuple
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


class TLSConfig:
    """
    TLS configuration for secure HTTPS communication.
    
    Manages TLS certificates, protocol versions, and cipher suites
    for secure API endpoints.
    """
    
    def __init__(
        self,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        min_tls_version: str = "TLSv1_2",
        verify_client: bool = False
    ):
        """
        Initialize TLS configuration.
        
        Args:
            cert_path: Path to server certificate file
            key_path: Path to server private key file
            ca_cert_path: Path to CA certificate for client verification
            min_tls_version: Minimum TLS version (TLSv1_2 or TLSv1_3)
            verify_client: Whether to verify client certificates
        """
        self.cert_path = Path(cert_path) if cert_path else None
        self.key_path = Path(key_path) if key_path else None
        self.ca_cert_path = Path(ca_cert_path) if ca_cert_path else None
        self.min_tls_version = min_tls_version
        self.verify_client = verify_client
        self._context: Optional[ssl.SSLContext] = None
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate TLS configuration."""
        if self.cert_path and not self.cert_path.exists():
            logger.warning(f"Certificate file not found: {self.cert_path}")
        
        if self.key_path and not self.key_path.exists():
            logger.warning(f"Private key file not found: {self.key_path}")
        
        if self.ca_cert_path and not self.ca_cert_path.exists():
            logger.warning(f"CA certificate file not found: {self.ca_cert_path}")
        
        # Validate TLS version
        valid_versions = {"TLSv1_2", "TLSv1_3"}
        if self.min_tls_version not in valid_versions:
            logger.warning(
                f"Invalid TLS version: {self.min_tls_version}. "
                f"Using default: TLSv1_2"
            )
            self.min_tls_version = "TLSv1_2"
    
    def create_context(self) -> ssl.SSLContext:
        """
        Create an SSL context with the configured settings.
        
        Returns:
            Configured SSL context for HTTPS
        """
        if self._context is not None:
            return self._context
        
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Set minimum TLS version
        if self.min_tls_version == "TLSv1_3":
            context.minimum_version = ssl.TLSVersion.TLSv1_3
        else:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Load certificate and key if provided
        if self.cert_path and self.key_path:
            try:
                context.load_cert_chain(
                    certfile=str(self.cert_path),
                    keyfile=str(self.key_path)
                )
                logger.info("Loaded TLS certificate and key")
            except Exception as e:
                logger.error(f"Failed to load TLS certificate: {e}")
                raise
        
        # Load CA certificate for client verification if provided
        if self.ca_cert_path:
            try:
                context.load_verify_locations(str(self.ca_cert_path))
                if self.verify_client:
                    context.verify_mode = ssl.CERT_REQUIRED
                logger.info("Loaded CA certificate for client verification")
            except Exception as e:
                logger.error(f"Failed to load CA certificate: {e}")
                raise
        
        # Configure cipher suites for security
        context.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:"
            "ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:"
            "DH+AES:RSA+AESGCM:RSA+AES:!aNULL:!MD5:!DSS"
        )
        
        # Enable OCSP stapling if supported
        try:
            context.options |= ssl.OP_NO_COMPRESSION
            context.options |= ssl.OP_NO_SSLv2
            context.options |= ssl.OP_NO_SSLv3
            context.options |= ssl.OP_NO_TLSv1
            context.options |= ssl.OP_NO_TLSv1_1
        except AttributeError:
            # Some Python versions don't have all options
            pass
        
        self._context = context
        return context
    
    def is_enabled(self) -> bool:
        """Check if TLS is enabled (cert and key files exist)."""
        return bool(self.cert_path and self.key_path and 
                   self.cert_path.exists() and self.key_path.exists())
    
    def get_config_dict(self) -> dict:
        """Get TLS configuration as a dictionary for logging."""
        return {
            "enabled": self.is_enabled(),
            "min_tls_version": self.min_tls_version,
            "verify_client": self.verify_client,
            "cert_path": str(self.cert_path) if self.cert_path else None,
            "key_path": str(self.key_path) if self.key_path else None,
            "ca_cert_path": str(self.ca_cert_path) if self.ca_cert_path else None,
        }


def create_tls_config() -> TLSConfig:
    """
    Create a TLS configuration from environment settings.
    
    Returns:
        Configured TLSConfig instance
    """
    return TLSConfig(
        cert_path=settings.tls_cert_path if hasattr(settings, 'tls_cert_path') else None,
        key_path=settings.tls_key_path if hasattr(settings, 'tls_key_path') else None,
        ca_cert_path=settings.tls_ca_cert_path if hasattr(settings, 'tls_ca_cert_path') else None,
        min_tls_version="TLSv1_2",
        verify_client=False
    )


def create_tls_context() -> Optional[ssl.SSLContext]:
    """
    Create an SSL context for HTTPS endpoints.
    
    Returns:
        SSL context if TLS is enabled, None otherwise
    """
    tls_config = create_tls_config()
    
    if tls_config.is_enabled():
        return tls_config.create_context()
    
    logger.warning("TLS is not enabled. API endpoints will use HTTP.")
    return None
