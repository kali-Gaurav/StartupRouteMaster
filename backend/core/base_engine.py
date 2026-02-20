"""
Base Engine Blueprint - Shared patterns for all engine implementations

Consolidates common patterns from:
- routing/engine.py (RailwayRouteEngine)
- pricing/engine.py (DynamicPricingEngine)
- inventory/seat_allocator.py (AdvancedSeatAllocationEngine)
- cache/manager.py (MultiLayerCache)

Features:
- Feature flag management
- Mode detection (OFFLINE/HYBRID/ONLINE)
- Startup logging
- Health checks
- Error handling
- Metrics tracking
"""

import logging
from typing import Dict, Optional, Any, List
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime

from .metrics import MetricsCollector, PerformanceMetricsCollector
from .data_structures import EngineMode

logger = logging.getLogger(__name__)


class EngineStatus(Enum):
    """Engine operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class FeatureDetector:
    """
    Detects available features based on configuration and environment.

    Checks:
    - API availability
    - Configuration flags
    - Dependency status
    - Network connectivity
    """

    def __init__(self):
        """Initialize feature detector."""
        self.features: Dict[str, bool] = {}
        self.detected_at = datetime.utcnow()

    def detect_feature(self, name: str, check_fn) -> bool:
        """
        Detect if a feature is available.

        Args:
            name: Feature name
            check_fn: Function that returns True if feature available

        Returns:
            Whether feature is available
        """
        try:
            available = check_fn()
            self.features[name] = available
            logger.debug(f"Feature {name}: {'✓ Available' if available else '✗ Unavailable'}")
            return available
        except Exception as e:
            logger.warning(f"Error detecting feature {name}: {e}")
            self.features[name] = False
            return False

    def get_mode(self) -> EngineMode:
        """
        Determine overall engine mode based on detected features.

        Returns:
            EngineMode.OFFLINE, HYBRID, or ONLINE
        """
        available_count = sum(1 for v in self.features.values() if v)
        total_count = len(self.features)

        if total_count == 0:
            return EngineMode.OFFLINE

        availability_ratio = available_count / total_count

        if availability_ratio == 0:
            return EngineMode.OFFLINE
        elif availability_ratio == 1:
            return EngineMode.ONLINE
        else:
            return EngineMode.HYBRID

    def get_status(self) -> Dict[str, Any]:
        """Get feature detection status."""
        return {
            'features': self.features,
            'mode': self.get_mode().value,
            'detected_at': self.detected_at.isoformat(),
            'availability_ratio': sum(1 for v in self.features.values() if v) / max(1, len(self.features)),
        }


class BaseEngine(ABC):
    """
    Abstract base class for all engine implementations.

    Provides:
    - Common initialization pattern
    - Feature detection
    - Startup logging
    - Health checking
    - Metrics tracking
    - Status reporting
    """

    def __init__(self, engine_name: str, engine_type: str = "generic"):
        """
        Initialize base engine.

        Args:
            engine_name: Human-readable name (e.g., 'RailwayRouteEngine')
            engine_type: Engine category (e.g., 'routing', 'pricing', 'caching')
        """
        self.engine_name = engine_name
        self.engine_type = engine_type
        self.status = EngineStatus.INITIALIZING
        self.created_at = datetime.utcnow()
        self.last_health_check = None

        # Feature management
        self.feature_detector = FeatureDetector()
        self.mode = EngineMode.OFFLINE

        # Metrics
        self.metrics = PerformanceMetricsCollector(
            name=f"{engine_type}_engine",
            window_size=1000
        )

        # Configuration
        self.config: Dict[str, Any] = {}

    # =========================================================================
    # FEATURE DETECTION & MODE MANAGEMENT
    # =========================================================================

    @abstractmethod
    async def detect_available_features(self):
        """
        Auto-detect available features based on configuration/environment.

        Subclasses must implement to detect their specific features.
        """
        pass

    async def initialize_features(self):
        """Initialize all features."""
        logger.info(f"Detecting available features for {self.engine_name}...")
        await self.detect_available_features()

        # Determine operating mode
        self.mode = self.feature_detector.get_mode()
        logger.info(f"Operating mode: {self.mode.value.upper()}")

    # =========================================================================
    # STARTUP & SHUTDOWN
    # =========================================================================

    async def startup(self):
        """
        Initialize and prepare engine for operation.

        Called once during application startup.
        """
        try:
            logger.info(f"Starting {self.engine_name}...")
            await self.initialize_features()
            await self._post_startup()
            self.status = EngineStatus.READY
            self._log_startup_status()
            logger.info(f"✓ {self.engine_name} started successfully")
        except Exception as e:
            logger.error(f"✗ Failed to start {self.engine_name}: {e}")
            self.status = EngineStatus.UNAVAILABLE
            raise

    async def _post_startup(self):
        """
        Hook for subclasses to perform additional startup tasks.

        Override in subclasses if needed.
        """
        pass

    async def shutdown(self):
        """
        Clean up resources and prepare for shutdown.

        Called during application shutdown.
        """
        logger.info(f"Shutting down {self.engine_name}...")
        await self._pre_shutdown()
        self.status = EngineStatus.UNAVAILABLE
        logger.info(f"✓ {self.engine_name} shut down")

    async def _pre_shutdown(self):
        """
        Hook for subclasses to perform cleanup tasks.

        Override in subclasses if needed.
        """
        pass

    # =========================================================================
    # STATUS & HEALTH CHECKING
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary
        """
        self.last_health_check = datetime.utcnow()

        return {
            'engine_name': self.engine_name,
            'status': self.status.value,
            'mode': self.mode.value,
            'uptime_seconds': (datetime.utcnow() - self.created_at).total_seconds(),
            'last_health_check': self.last_health_check.isoformat(),
            'features': self.feature_detector.get_status(),
            'healthy': self.status == EngineStatus.READY,
        }

    def is_ready(self) -> bool:
        """Check if engine is ready to process requests."""
        return self.status == EngineStatus.READY

    def is_degraded(self) -> bool:
        """Check if engine is in degraded mode."""
        return self.status == EngineStatus.DEGRADED

    # =========================================================================
    # LOGGING
    # =========================================================================

    def _log_startup_status(self):
        """Log detailed startup status."""
        logger.info("=" * 70)
        logger.info(f"🚀 {self.engine_name} - Startup Complete")
        logger.info(f"📍 Type: {self.engine_type}")
        logger.info(f"🔄 Mode: {self.mode.value.upper()}")

        feature_status = self.feature_detector.get_status()
        logger.info(f"📊 Features:")
        for feature, available in feature_status['features'].items():
            symbol = "🟢" if available else "🔴"
            logger.info(f"   {symbol} {feature}")

        logger.info("=" * 70)

    def log_operation(self, operation: str, duration_ms: float, success: bool = True):
        """
        Log an operation execution.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
        """
        self.metrics.record_operation_duration(operation, duration_ms)
        if not success:
            self.metrics.record_operation_error(operation)

        symbol = "✓" if success else "✗"
        status = "success" if success else "failed"
        logger.debug(f"{symbol} {operation}: {duration_ms:.1f}ms ({status})")

    # =========================================================================
    # METRICS & MONITORING
    # =========================================================================

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return self.metrics.get_summary()

    def log_metrics_summary(self):
        """Log metrics summary."""
        logger.info(f"Metrics for {self.engine_name}:")
        self.metrics.log_summary()

    # =========================================================================
    # STATUS REPORTING
    # =========================================================================

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report."""
        health = self.health_check()
        return {
            **health,
            'metrics': self.get_metrics_summary(),
            'config': {k: v for k, v in self.config.items() if k != 'password'}  # Redact passwords
        }

    def log_status_report(self):
        """Log comprehensive status report."""
        report = self.get_status_report()
        logger.info(f"Status Report for {self.engine_name}:")
        logger.info(f"  Status: {report['status']}")
        logger.info(f"  Mode: {report['mode']}")
        logger.info(f"  Uptime: {report['uptime_seconds']:.1f}s")


# ==============================================================================
# FEATURE FLAG MANAGER
# ==============================================================================

class FeatureFlagManager:
    """
    Manages feature flags for engine behavior control.

    Supports:
    - Boolean flags for on/off switching
    - String flags for configuration choices
    - Numeric flags for thresholds
    """

    def __init__(self):
        """Initialize feature flag manager."""
        self.flags: Dict[str, Any] = {}

    def set_flag(self, name: str, value: Any):
        """Set a feature flag."""
        self.flags[name] = value
        logger.debug(f"Feature flag {name} = {value}")

    def get_flag(self, name: str, default: Any = None) -> Any:
        """Get a feature flag value."""
        return self.flags.get(name, default)

    def is_enabled(self, name: str) -> bool:
        """Check if a boolean feature is enabled."""
        return bool(self.flags.get(name, False))

    def load_from_dict(self, flags_dict: Dict[str, Any]):
        """Load flags from dictionary."""
        self.flags.update(flags_dict)
        logger.info(f"Loaded {len(flags_dict)} feature flags")

    def load_from_env(self, prefix: str = "FEATURE_"):
        """Load flags from environment variables."""
        import os
        count = 0
        for env_var, value in os.environ.items():
            if env_var.startswith(prefix):
                flag_name = env_var[len(prefix):].lower()
                # Parse value
                if value.lower() in ['true', '1', 'yes', 'on']:
                    self.flags[flag_name] = True
                elif value.lower() in ['false', '0', 'no', 'off']:
                    self.flags[flag_name] = False
                else:
                    try:
                        self.flags[flag_name] = float(value)
                    except ValueError:
                        self.flags[flag_name] = value
                count += 1

        logger.info(f"Loaded {count} feature flags from environment")

    def get_all_flags(self) -> Dict[str, Any]:
        """Get all feature flags."""
        return dict(self.flags)
