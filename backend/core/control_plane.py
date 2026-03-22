import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional
from enum import IntEnum
from datetime import datetime

from core.providers import ServiceProvider, ServiceStatus
from core.container import container

logger = logging.getLogger("routemaster.control_plane")

class SystemLevel(IntEnum):
    NORMAL = 0
    ADVISORY = 1
    WARNING = 2
    CRITICAL = 3
    LOCKED = 4 # Emergency Lock / Kill Switch
    MAINTENANCE = 5

class ControlPlane(ServiceProvider):
    """
    Task 9: Unified Control Plane.
    Centralized Authority for System State, Feature Toggles, and Emergency Policies.
    """
    def __init__(self):
        super().__init__("control", version="1.0.0")
        self._level = SystemLevel.NORMAL
        self._features: Dict[str, bool] = {}
        self._local_cache_time = 0
        self._cache_ttl = 5 # 5 seconds local cache for rapid middleware checks
        
        # In-memory overrides (Emergency Policy)
        self._overrides: Dict[str, Any] = {}

    async def init(self):
        """IoC Lifecycle: Connect to Redis to sync global control state."""
        await self._sync_with_redis()
        logger.info("📡 IoC: ControlPlane Initialized.")

    async def _sync_with_redis(self):
        """Syncs local state with Redis global config."""
        try:
            cache = await container.get("cache", timeout=2.0)
            if not cache or not cache.redis:
                return

            # Sync System Level
            level_raw = await cache.redis.get("system:level")
            if level_raw:
                self._level = SystemLevel(int(level_raw))

            # Sync Feature Toggles
            features_raw = await cache.redis.get("system:features")
            if features_raw:
                self._features = json.loads(features_raw)
            else:
                # Default features if missing
                self._features = {
                    "search_api": True,
                    "ml_booking": True,
                    "auth_v2": True,
                    "analytics_mq": True,
                    "feedback_loop": True
                }
                await cache.redis.set("system:features", json.dumps(self._features))
            
            self._local_cache_time = time.time()
        except Exception as e:
            logger.error(f"ControlPlane sync error: {e}")

    async def get_level(self) -> SystemLevel:
        """Rapid Level Check with TTL Cache."""
        if time.time() - self._local_cache_time > self._cache_ttl:
            asyncio.create_task(self._sync_with_redis()) # Async refresh
        return self._level

    async def is_feature_enabled(self, feature_name: str) -> bool:
        """Checks if a specific feature toggle is active."""
        if time.time() - self._local_cache_time > self._cache_ttl:
            await self._sync_with_redis() # Sync wait for feature checks
        return self._features.get(feature_name, True)

    async def set_level(self, level: SystemLevel, user: str = "system", reason: str = "manual"):
        """Updates the system level globally."""
        old_level = self._level
        self._level = level
        
        try:
            cache = await container.get("cache")
            if cache and cache.redis:
                await cache.redis.set("system:level", str(int(level)))
                
                # Audit Log
                audit_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": user,
                    "action": "set_level",
                    "from": old_level.name,
                    "to": level.name,
                    "reason": reason
                }
                await cache.redis.lpush("system:audit", json.dumps(audit_entry))
                await cache.redis.ltrim("system:audit", 0, 999) # Keep last 1000
        except Exception as e:
            logger.error(f"Failed to propagate level change: {e}")
            
        logger.warning(f"🚨 SYSTEM STATE CHANGED: {old_level.name} -> {level.name} (by {user})")

    async def set_feature(self, feature_name: str, enabled: bool, user: str = "system"):
        """Toggles a feature globally."""
        self._features[feature_name] = enabled
        
        try:
            cache = await container.get("cache")
            if cache and cache.redis:
                await cache.redis.set("system:features", json.dumps(self._features))
                
                # Audit Log
                audit_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": user,
                    "action": "toggle_feature",
                    "feature": feature_name,
                    "enabled": enabled
                }
                await cache.redis.lpush("system:audit", json.dumps(audit_entry))
        except Exception as e:
            logger.error(f"Failed to propagate feature toggle: {e}")
            
        logger.info(f"⚙️ FEATURE TOGGLE: {feature_name} {'ENABLED' if enabled else 'DISABLED'} (by {user})")

    async def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves system audit logs from Redis."""
        try:
            cache = await container.get("cache")
            if cache and cache.redis:
                logs = await cache.redis.lrange("system:audit", 0, limit - 1)
                return [json.loads(l) for l in logs]
        except:
            pass
        return []

    async def rollback(self, user: str = "admin"):
        """Task 9: Reverts System Level and Features to the last known stable snapshot."""
        try:
            cache = await container.get("cache")
            if cache and cache.redis:
                snapshot_raw = await cache.redis.get("system:snapshot:stable")
                if not snapshot_raw:
                    logger.error("No stable snapshot available for rollback.")
                    return False
                
                snapshot = json.loads(snapshot_raw)
                self._level = SystemLevel(snapshot["level"])
                self._features = snapshot["features"]
                
                # Propagate
                await cache.redis.set("system:level", str(int(self._level)))
                await cache.redis.set("system:features", json.dumps(self._features))
                
                # Audit
                audit_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user": user,
                    "action": "rollback",
                    "reason": "System restore to last stable snapshot"
                }
                await cache.redis.lpush("system:audit", json.dumps(audit_entry))
                logger.warning(f"🔄 ROLLBACK EXECUTED: System restored to level {self._level.name}")
                return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
        return False

    async def save_stable_snapshot(self):
        """Saves current state as a 'stable' restore point."""
        try:
            cache = await container.get("cache")
            if cache and cache.redis:
                snapshot = {
                    "level": int(self._level),
                    "features": self._features,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await cache.redis.set("system:snapshot:stable", json.dumps(snapshot))
                logger.info("💾 ControlPlane: Stable snapshot saved.")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    async def apply_emergency_policy(self, policy_name: str, user: str = "system"):
        """
        Task 9: Apply pre-defined emergency states.
        Policies: 'LOCKDOWN', 'LITE_MODE', 'MAINTENANCE_ONLY'
        """
        if policy_name == "LOCKDOWN":
            await self.set_level(SystemLevel.LOCKED, user=user, reason="Emergency Lockdown Policy")
            # Disable all but core
            for f in self._features:
                if f != "auth_v2": self._features[f] = False
            await self._propagate_features()
            
        elif policy_name == "LITE_MODE":
            await self.set_level(SystemLevel.WARNING, user=user, reason="Load-Shedding Lite Mode")
            # Disable non-essentials
            self._features["ml_booking"] = False
            self._features["analytics_mq"] = False
            await self._propagate_features()

        logger.critical(f"🆘 EMERGENCY POLICY APPLIED: {policy_name}")

    async def _propagate_features(self):
        cache = await container.get("cache")
        if cache and cache.redis:
            await cache.redis.set("system:features", json.dumps(self._features))

    async def fallback(self):
        """In degraded mode, we revert to safest level (LOCKED or MAINTENANCE)."""
        await super().fallback()
        self._level = SystemLevel.WARNING # Safer default if cache fails
        logger.error("📉 ControlPlane in Degraded mode: Defaulting to WARNING state.")

# Global Instance and Container Registration
control_plane = ControlPlane()
container.register(control_plane)
