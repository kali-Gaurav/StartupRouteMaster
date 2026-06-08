"""
Secrets Management for the Contextual Availability Transformer (CAT) system.
Provides secure storage and rotation of API keys and credentials.
"""

import os
import logging
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Manages secrets for external API credentials and sensitive data.
    
    Supports environment-based secrets, file-based secrets, and
    integration with external secrets management systems.
    """
    
    def __init__(
        self,
        env_prefix: str = "CAT_",
        rotation_interval_days: int = 90,
        secrets_dir: Optional[str] = None
    ):
        """
        Initialize secrets manager.
        
        Args:
            env_prefix: Prefix for environment variables
            rotation_interval_days: Days between secret rotations
            secrets_dir: Directory for file-based secrets
        """
        self.env_prefix = env_prefix
        self.rotation_interval_days = rotation_interval_days
        self.secrets_dir = Path(secrets_dir) if secrets_dir else None
        self._cache: Dict[str, Any] = {}
        self._rotation_timestamps: Dict[str, float] = {}
        self._loaded_secrets: Dict[str, str] = {}
        
        # Load secrets from environment
        self._load_from_environment()
        
        # Load secrets from file if directory is configured
        if self.secrets_dir and self.secrets_dir.exists():
            self._load_from_file()
    
    def _load_from_environment(self) -> None:
        """Load secrets from environment variables."""
        # Event Calendar API credentials
        self._loaded_secrets["event_api_key"] = os.environ.get(
            f"{self.env_prefix}EVENT_API_KEY",
            os.environ.get("EVENT_API_KEY")
        )
        
        # Weather API credentials
        self._loaded_secrets["weather_api_key"] = os.environ.get(
            f"{self.env_prefix}WEATHER_API_KEY",
            os.environ.get("WEATHER_API_KEY")
        )
        
        # Database credentials
        self._loaded_secrets["database_password"] = os.environ.get(
            f"{self.env_prefix}DATABASE_PASSWORD",
            os.environ.get("DATABASE_PASSWORD")
        )
        
        # External service credentials
        self._loaded_secrets["external_api_secret"] = os.environ.get(
            f"{self.env_prefix}EXTERNAL_API_SECRET",
            os.environ.get("EXTERNAL_API_SECRET")
        )
        
        logger.info(f"Loaded {len(self._loaded_secrets)} secrets from environment")
    
    def _load_from_file(self) -> None:
        """Load secrets from file if directory is configured."""
        secrets_file = self.secrets_dir / "secrets.json"
        
        if secrets_file.exists():
            try:
                import json
                with open(secrets_file, 'r') as f:
                    file_secrets = json.load(f)
                
                # Merge with environment secrets
                for key, value in file_secrets.items():
                    if key not in self._loaded_secrets or not self._loaded_secrets[key]:
                        self._loaded_secrets[key] = value
                
                logger.info(f"Loaded secrets from {secrets_file}")
            except Exception as e:
                logger.error(f"Failed to load secrets from file: {e}")
    
    def get_secret(self, name: str) -> Optional[str]:
        """
        Get a secret by name.
        
        Args:
            name: Secret name (e.g., 'event_api_key', 'weather_api_key')
            
        Returns:
            Secret value or None if not found
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]
        
        # Get from loaded secrets
        value = self._loaded_secrets.get(name)
        
        if value:
            # Cache the value
            self._cache[name] = value
            return value
        
        return None
    
    def set_secret(self, name: str, value: str) -> None:
        """
        Set a secret value.
        
        Args:
            name: Secret name
            value: Secret value
        """
        self._loaded_secrets[name] = value
        self._cache[name] = value
        
        logger.info(f"Set secret: {name}")
    
    def rotate_secret(self, name: str) -> str:
        """
        Rotate a secret and return the new value.
        
        Args:
            name: Secret name to rotate
            
        Returns:
            New secret value
        """
        # Generate new secret
        new_value = self._generate_secret()
        
        # Set new value
        self.set_secret(name, new_value)
        
        # Update rotation timestamp
        self._rotation_timestamps[name] = time.time()
        
        logger.info(f"Rotated secret: {name}")
        
        return new_value
    
    def _generate_secret(self) -> str:
        """
        Generate a secure random secret.
        
        Returns:
            Generated secret string
        """
        import secrets
        return secrets.token_urlsafe(32)
    
    def check_rotation_needed(self, name: str) -> bool:
        """
        Check if a secret needs rotation.
        
        Args:
            name: Secret name
            
        Returns:
            True if rotation is needed, False otherwise
        """
        if name not in self._rotation_timestamps:
            # Never rotated, check if it's old
            return False
        
        last_rotation = self._rotation_timestamps[name]
        days_since_rotation = (time.time() - last_rotation) / (24 * 3600)
        
        return days_since_rotation >= self.rotation_interval_days
    
    def get_rotation_status(self) -> Dict[str, Any]:
        """
        Get rotation status for all secrets.
        
        Returns:
            Dictionary with rotation status for each secret
        """
        status = {}
        
        for name in self._loaded_secrets:
            status[name] = {
                "rotated": name in self._rotation_timestamps,
                "rotation_needed": self.check_rotation_needed(name),
                "days_since_rotation": (
                    (time.time() - self._rotation_timestamps[name]) / (24 * 3600)
                    if name in self._rotation_timestamps else None
                )
            }
        
        return status
    
    def validate_secret(self, name: str, value: str) -> bool:
        """
        Validate a secret value.
        
        Args:
            name: Secret name
            value: Secret value to validate
            
        Returns:
            True if valid, False otherwise
        """
        stored = self.get_secret(name)
        
        if stored is None:
            return False
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(stored, value)
    
    def hash_secret(self, value: str) -> str:
        """
        Hash a secret for secure storage.
        
        Args:
            value: Secret value to hash
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(value.encode()).hexdigest()
    
    def get_all_secrets(self) -> Dict[str, Optional[str]]:
        """
        Get all loaded secrets.
        
        Returns:
            Dictionary of all secrets (values are masked for security)
        """
        return {
            name: "***" if value else None
            for name, value in self._loaded_secrets.items()
        }
    
    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cache.clear()
        logger.debug("Cleared secrets cache")


def create_secrets_manager() -> SecretsManager:
    """
    Create a secrets manager instance from environment settings.
    
    Returns:
        Configured SecretsManager instance
    """
    secrets_dir = os.environ.get("CAT_SECRETS_DIR")
    
    return SecretsManager(
        env_prefix="CAT_",
        rotation_interval_days=90,
        secrets_dir=secrets_dir
    )
