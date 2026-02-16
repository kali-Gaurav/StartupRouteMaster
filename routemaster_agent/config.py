"""
Configuration module for RouteMaster Agent.

Loads and manages environment variables from .env file.
Provides centralized access to all configuration settings.
"""

import os
import logging
from typing import List, Optional
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Find .env file in project root
    root_dir = Path(__file__).parent.parent
    env_file = root_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Also check current directory
        load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class GeminiConfig:
    """Configuration for Gemini API."""

    @staticmethod
    def get_api_keys() -> List[str]:
        """
        Get all configured Gemini API keys.
        
        Returns list of API keys in order of preference.
        Checks GEMINI_API_KEY1-5, then falls back to GEMINI_API_KEY.
        
        Returns:
            List of API keys (empty if none configured)
        """
        keys = []
        
        # Try individual keys first
        for i in range(1, 6):
            key = os.getenv(f"GEMINI_API_KEY{i}")
            if key:
                keys.append(key)
        
        # Fall back to single key
        if not keys:
            single_key = os.getenv("GEMINI_API_KEY")
            if single_key:
                keys.append(single_key)
        
        return keys

    @staticmethod
    def get_model() -> str:
        """
        Get Gemini model name.
        
        Returns:
            Model name (default: gemini-pro-vision)
        """
        return os.getenv("GEMINI_MODEL", "gemini-pro-vision")

    @staticmethod
    def get_timeout() -> int:
        """
        Get API call timeout in seconds.
        
        Returns:
            Timeout in seconds (default: 30)
        """
        return int(os.getenv("GEMINI_TIMEOUT", "30"))

    @staticmethod
    def is_enabled() -> bool:
        """
        Check if Gemini is enabled (has at least one API key).
        
        Returns:
            True if at least one API key is configured
        """
        return len(GeminiConfig.get_api_keys()) > 0


class DatabaseConfig:
    """Configuration for database."""

    @staticmethod
    def get_url() -> str:
        """
        Get database URL.
        
        Returns:
            Database connection URL
        """
        return os.getenv("DATABASE_URL", "postgresql://localhost/routemaster")

    @staticmethod
    def get_echo() -> bool:
        """
        Get SQL echo setting (logs all SQL queries).
        
        Returns:
            True to log SQL queries
        """
        return os.getenv("DATABASE_ECHO", "false").lower() == "true"


class ProxyConfig:
    """Configuration for proxy management."""

    @staticmethod
    def get_proxies() -> List[str]:
        """
        Get list of configured proxies.
        
        Returns:
            List of proxy URLs (empty if none configured)
        """
        proxies_str = os.getenv("PROXIES", "")
        if not proxies_str:
            return []
        return [p.strip() for p in proxies_str.split(",") if p.strip()]

    @staticmethod
    def get_timeout() -> int:
        """
        Get proxy request timeout.
        
        Returns:
            Timeout in seconds (default: 5)
        """
        return int(os.getenv("PROXY_TIMEOUT", "5"))

    @staticmethod
    def get_fail_threshold() -> float:
        """
        Get proxy failure threshold.
        
        Returns:
            Failure rate threshold (0.0-1.0, default: 0.5)
        """
        return float(os.getenv("PROXY_FAIL_THRESHOLD", "0.5"))


class RMAConfig:
    """Configuration for RouteMaster Agent."""

    @staticmethod
    def get_proxy_check_interval() -> int:
        """
        Get proxy health check interval.
        
        Returns:
            Interval in seconds (default: 300)
        """
        return int(os.getenv("RMA_PROXY_CHECK_INTERVAL", "300"))

    @staticmethod
    def get_proxy_check_timeout() -> int:
        """
        Get proxy health check timeout.
        
        Returns:
            Timeout in seconds (default: 5)
        """
        return int(os.getenv("RMA_PROXY_CHECK_TIMEOUT", "5"))

    @staticmethod
    def get_proxy_fail_threshold() -> float:
        """
        Get proxy failure threshold for RMA.
        
        Returns:
            Failure rate threshold (0.0-1.0, default: 0.5)
        """
        return float(os.getenv("RMA_PROXY_FAIL_THRESHOLD", "0.5"))

    @staticmethod
    def is_disha_enabled() -> bool:
        """
        Check if Disha verification is enabled.
        
        Returns:
            True if enabled (default: true)
        """
        return os.getenv("ENABLE_DISHA_VERIFICATION", "true").lower() == "true"

    @staticmethod
    def is_reliability_scheduler_enabled() -> bool:
        """
        Check if reliability scheduler is enabled.
        
        Returns:
            True if enabled (default: true)
        """
        return os.getenv("ENABLE_RELIABILITY_SCHEDULER", "true").lower() == "true"

    @staticmethod
    def is_proxy_monitoring_enabled() -> bool:
        """
        Check if proxy monitoring is enabled.
        
        Returns:
            True if enabled (default: true)
        """
        return os.getenv("ENABLE_PROXY_MONITORING", "true").lower() == "true"


class LoggingConfig:
    """Configuration for logging."""

    @staticmethod
    def get_level() -> str:
        """
        Get logging level.
        
        Returns:
            Logging level (default: INFO)
        """
        return os.getenv("LOG_LEVEL", "INFO")

    @staticmethod
    def get_file() -> str:
        """
        Get log file path.
        
        Returns:
            Log file path (default: logs/routemaster.log)
        """
        return os.getenv("LOG_FILE", "logs/routemaster.log")


def print_config() -> None:
    """
    Print current configuration status.
    Useful for debugging configuration issues.
    """
    print("\n=== RouteMaster Agent Configuration ===\n")
    
    # Gemini
    gemini_keys = GeminiConfig.get_api_keys()
    print(f"Gemini API Keys: {len(gemini_keys)} key(s) configured")
    print(f"  - Model: {GeminiConfig.get_model()}")
    print(f"  - Enabled: {GeminiConfig.is_enabled()}")
    print(f"  - Timeout: {GeminiConfig.get_timeout()}s")
    
    # Database
    print(f"\nDatabase:")
    print(f"  - URL: {DatabaseConfig.get_url()}")
    print(f"  - Echo SQL: {DatabaseConfig.get_echo()}")
    
    # Proxy
    proxies = ProxyConfig.get_proxies()
    print(f"\nProxy:")
    print(f"  - Configured: {len(proxies)} proxy/proxies")
    print(f"  - Timeout: {ProxyConfig.get_timeout()}s")
    print(f"  - Fail Threshold: {ProxyConfig.get_fail_threshold()}")
    
    # RMA
    print(f"\nRouteMaster Agent:")
    print(f"  - Proxy Check Interval: {RMAConfig.get_proxy_check_interval()}s")
    print(f"  - Disha Enabled: {RMAConfig.is_disha_enabled()}")
    print(f"  - Reliability Scheduler: {RMAConfig.is_reliability_scheduler_enabled()}")
    print(f"  - Proxy Monitoring: {RMAConfig.is_proxy_monitoring_enabled()}")
    
    # Logging
    print(f"\nLogging:")
    print(f"  - Level: {LoggingConfig.get_level()}")
    print(f"  - File: {LoggingConfig.get_file()}")
    
    print("\n" + "=" * 40 + "\n")


if __name__ == "__main__":
    print_config()
