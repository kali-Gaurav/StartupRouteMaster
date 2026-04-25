from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from database.config import Config as DatabaseConfig

__all__ = [
    "BootstrapConfigError",
    "BootstrapSettings",
    "Config",
    "get_bootstrap_settings",
]


Config = DatabaseConfig


class BootstrapConfigError(RuntimeError):
    """Raised when bootstrap configuration is invalid."""


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BootstrapSettings:
    environment: str
    host: str
    port: int
    log_level: str
    media_root: Path
    media_sos_root: Path
    use_simple_lifespan: bool
    allow_degraded_boot: bool
    register_api_routes: bool
    enable_worker_swarm: bool
    enable_worker_watchdog: bool
    heartbeat_log_path: Path
    route_engine_init_timeout_sec: float

    @classmethod
    def from_env(cls) -> "BootstrapSettings":
        base_dir = Path(Config.BASE_DIR)
        media_root = Path(os.getenv("MEDIA_ROOT", str(base_dir / "media"))).resolve()
        heartbeat_log_path = Path(
            os.getenv("HEARTBEAT_WORKER_LOG", str(base_dir / "heartbeat_worker.log"))
        ).resolve()

        return cls(
            environment=str(getattr(Config, "ENVIRONMENT", "development")).lower(),
            host=os.getenv("HOST", "0.0.0.0").strip(),
            port=int(os.getenv("PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", str(getattr(Config, "LOG_LEVEL", "INFO"))).upper(),
            media_root=media_root,
            media_sos_root=media_root / "sos",
            use_simple_lifespan=_get_env_bool(
                "USE_SIMPLE_LIFESPAN",
                str(getattr(Config, "ENVIRONMENT", "development")).lower() != "production",
            ),
            allow_degraded_boot=_get_env_bool("ALLOW_DEGRADED_BOOT", True),
            register_api_routes=_get_env_bool("REGISTER_API_ROUTES", True),
            enable_worker_swarm=_get_env_bool("ENABLE_WORKER_SWARM", True),
            enable_worker_watchdog=_get_env_bool("ENABLE_WORKER_WATCHDOG", True),
            heartbeat_log_path=heartbeat_log_path,
            route_engine_init_timeout_sec=float(os.getenv("ROUTE_ENGINE_INIT_TIMEOUT_SEC", "1.5")),
        ).validate()

    def validate(self) -> "BootstrapSettings":
        allowed_environments = {"development", "test", "testing", "staging", "production"}
        if self.environment not in allowed_environments:
            raise BootstrapConfigError(
                f"Invalid ENVIRONMENT '{self.environment}'. Expected one of {sorted(allowed_environments)}."
            )

        if not (1 <= self.port <= 65535):
            raise BootstrapConfigError(f"Invalid PORT '{self.port}'. Must be between 1 and 65535.")

        if not self.host:
            raise BootstrapConfigError("HOST cannot be empty.")

        if self.route_engine_init_timeout_sec <= 0:
            raise BootstrapConfigError("ROUTE_ENGINE_INIT_TIMEOUT_SEC must be greater than zero.")

        allowed_log_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if self.log_level not in allowed_log_levels:
            raise BootstrapConfigError(
                f"Invalid LOG_LEVEL '{self.log_level}'. Expected one of {sorted(allowed_log_levels)}."
            )

        return self


@lru_cache(maxsize=1)
def get_bootstrap_settings() -> BootstrapSettings:
    return BootstrapSettings.from_env()
