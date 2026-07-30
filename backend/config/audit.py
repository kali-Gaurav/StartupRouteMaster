"""Audit logging configuration."""

from typing import Optional
from pydantic import BaseSettings


class AuditConfig(BaseSettings):
    """Audit logging configuration."""

    # Enable/disable audit logging
    enabled: bool = True

    # Audit log retention policy (days)
    retention_days: int = 30

    # Enable detailed logging
    verbose: bool = False

    # Batch audit writes (for performance)
    batch_size: int = 100
    batch_timeout_ms: int = 5000

    # Tables to exclude from auditing
    excluded_tables: list = [
        "audit_log",
        "audit_logs",
        "alembic_version",
    ]

    class Config:
        env_prefix = "AUDIT_"
        case_sensitive = False


# Global audit config instance
_audit_config: Optional[AuditConfig] = None


def get_audit_config() -> AuditConfig:
    """Get audit configuration."""
    global _audit_config
    if _audit_config is None:
        _audit_config = AuditConfig()
    return _audit_config


def set_audit_config(config: AuditConfig):
    """Set audit configuration."""
    global _audit_config
    _audit_config = config
