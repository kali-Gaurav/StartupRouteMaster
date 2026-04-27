"""
Telegram Bot Configuration
==========================
Production-ready configuration management with environment-based setup.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import os
import json


class BotMode(Enum):
    """Bot operation modes."""
    POLLING = "polling"
    WEBHOOK = "webhook"
    MIXED = "mixed"


@dataclass
class TelegramBotConfig:
    """Main bot configuration."""
    
    # Core settings
    bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", ""))
    enabled: bool = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_ENABLED", "true").lower() in ("1", "true", "yes"))
    bot_mode: BotMode = BotMode.POLLING
    webhook_url: Optional[str] = None
    webhook_path: str = "/webhooks/telegram"
    
    # Performance settings
    max_concurrent_updates: int = 10
    message_batch_size: int = 10
    processing_timeout: float = 30.0
    
    # Session settings
    session_ttl_hours: int = 24
    state_ttl_seconds: int = 3600
    
    # Feature flags
    enable_nlp: bool = True
    enable_context_memory: bool = True
    enable_suggestions: bool = True
    enable_analytics: bool = True
    
    # Rate limiting
    rate_limit_messages: int = 30
    rate_limit_window_seconds: int = 60
    
    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 10.0
    
    # Logging
    log_level: str = "INFO"
    log_chat_id: Optional[int] = None
    
    @classmethod
    def from_env(cls) -> "TelegramBotConfig":
        """Create config from environment variables."""
        bot_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        return cls(
            bot_token=bot_token,
            enabled=os.getenv("TELEGRAM_BOT_ENABLED", "true").lower() in ("1", "true", "yes"),
            bot_mode=BotMode(os.getenv("TELEGRAM_BOT_MODE", "polling").lower()),
            webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL", None),
            max_concurrent_updates=int(os.getenv("TELEGRAM_MAX_CONCURRENT", "10")),
            session_ttl_hours=int(os.getenv("TELEGRAM_SESSION_TTL", "24")),
            enable_nlp=os.getenv("TELEGRAM_ENABLE_NLP", "true").lower() == "true",
            enable_context_memory=os.getenv("TELEGRAM_ENABLE_CONTEXT", "true").lower() == "true",
            enable_suggestions=os.getenv("TELEGRAM_ENABLE_SUGGESTIONS", "true").lower() == "true",
            rate_limit_messages=int(os.getenv("TELEGRAM_RATE_LIMIT", "30")),
            max_retries=int(os.getenv("TELEGRAM_MAX_RETRIES", "3")),
            log_level=os.getenv("TELEGRAM_LOG_LEVEL", "INFO"),
        )
    
    @property
    def mode(self) -> str:
        return self.bot_mode.name

    def validate(self) -> Dict[str, Any]:
        """Validate configuration."""
        errors = []
        
        if not self.bot_token:
            errors.append("TELEGRAM_TOKEN is required")
        
        if self.bot_mode == BotMode.WEBHOOK and not self.webhook_url:
            errors.append("WEBHOOK_URL is required for webhook mode")
        
        if self.max_concurrent_updates < 1:
            errors.append("MAX_CONCURRENT_UPDATES must be >= 1")
        
        if self.max_retries < 0:
            errors.append("MAX_RETRIES must be >= 0")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


@dataclass
class FeatureConfig:
    """Feature-specific configuration."""
    
    # Search features
    search_max_results: int = 10
    search_default_radius_km: int = 50
    
    # Booking features
    booking_max_passengers: int = 6
    booking_payment_timeout_minutes: int = 15
    
    # Notification features
    notification_pnr_alerts: bool = True
    notification_delay_alerts: bool = True
    notification_cancellation_alerts: bool = True
    
    # SOS features
    sos_emergency_contacts: int = 3
    sos_location_sharing: bool = True
    
    @classmethod
    def from_env(cls) -> "FeatureConfig":
        return cls(
            search_max_results=int(os.getenv("TELEGRAM_SEARCH_MAX_RESULTS", "10")),
            search_default_radius_km=int(os.getenv("TELEGRAM_SEARCH_RADIUS", "50")),
            booking_max_passengers=int(os.getenv("TELEGRAM_BOOKING_MAX_PASSENGERS", "6")),
            booking_payment_timeout_minutes=int(os.getenv("TELEGRAM_PAYMENT_TIMEOUT", "15")),
            notification_pnr_alerts=os.getenv("TELEGRAM_PNR_ALERTS", "true").lower() == "true",
            notification_delay_alerts=os.getenv("TELEGRAM_DELAY_ALERTS", "true").lower() == "true",
            sos_emergency_contacts=int(os.getenv("TELEGRAM_SOS_CONTACTS", "3")),
        )


# Global config instances
bot_config = TelegramBotConfig.from_env()
feature_config = FeatureConfig.from_env()