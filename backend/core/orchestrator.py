import asyncio
import logging
import time
import traceback
import random
import threading
import json
import os
from datetime import datetime
from enum import IntEnum
from typing import Any, cast, Dict, List, Callable, Coroutine, Optional, Set, Type
from dataclasses import dataclass, field

class EngineTier(IntEnum):
    TIER_1_ULTRA_TURBO = 1
    TIER_2_TURBO = 2
    TIER_3_RAPTOR = 3

@dataclass
class EngineMetadata:
    name: str
    tier: EngineTier
    enabled: bool = True
    instance: Optional[Any] = None
    # [Task 21.3] Health Monitoring
    last_health_check: float = 0.0
    is_healthy: bool = True
    error_count: int = 0
    # [Task 21.7] Capability Manifest
    capabilities: List[str] = field(default_factory=list) # ["direct", "1-transfer", "multi-transfer"]
    # [Task 21.8] Weighted Selection
    weight: int = 100
    # [Task 21.9] Tier-Based Timeout
    custom_timeout_ms: Optional[int] = None

class EngineRegistry:
    """[Task 21] Central registry for all routing engines."""
    def __init__(self, persistence_path: str = "data/engine_registry.json"):
        self.engines: Dict[str, EngineMetadata] = {}
        self.persistence_path = persistence_path
        self._last_drop_time = 0
        self._load_state()

    def register(self, name: str, tier: EngineTier, instance: Any = None, capabilities: Optional[List[str]] = None, weight: int = 100):
        if name in self.engines:
            self.engines[name].instance = instance
            self.engines[name].tier = tier
            self.engines[name].capabilities = capabilities or []
            self.engines[name].weight = weight
        else:
            self.engines[name] = EngineMetadata(name=name, tier=tier, instance=instance, capabilities=capabilities or [], weight=weight)
        logger.info(f"📍 EngineRegistry: Registered {name} (Tier {tier.value})")

    def get_engines_by_tier(self, tier: EngineTier) -> List[Any]:
        # [Task 21.8] Sort by weight
        sorted_meta = sorted(
            [e for e in self.engines.values() if e.tier == tier and e.enabled and e.is_healthy and e.instance],
            key=lambda x: x.weight, reverse=True
        )
        return [e.instance for e in sorted_meta]

    def set_enabled(self, name: str, enabled: bool):
        if name in self.engines:
            self.engines[name].enabled = enabled
            logger.info(f"📍 EngineRegistry: Engine {name} {'ENABLED' if enabled else 'DISABLED'}")
            self._save_state()

    def report_health(self, name: str, is_healthy: bool):
        if name in self.engines:
            e = self.engines[name]
            e.is_healthy = is_healthy
            e.last_health_check = time.time()
            if not is_healthy: e.error_count += 1
            else: e.error_count = 0

    def disable_tier(self, tier: EngineTier):
        for e in self.engines.values():
            if e.tier == tier: e.enabled = False
        self._save_state()

    def get_tier_status(self) -> Dict[int, bool]:
        """[Task 24.1] Get availability of each tier."""
        status = {}
        for tier in EngineTier:
            enabled_count = sum(1 for e in self.engines.values() if e.tier == tier and e.enabled and e.is_healthy)
            status[tier.value] = enabled_count > 0
        return status

    def check_and_drop_tiers(self):
        """[Analysis Only] Log surge levels without affecting operation."""
        from core.resource_monitor import resource_monitor, SurgeLevel
        level = resource_monitor.get_surge_level()
        if level != SurgeLevel.NORMAL:
            logger.info(f"📊 Surge Analysis: System is in {level.name} state. COMPLETE SEARCH MAINTAINED.")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            state = {name: e.enabled for name, e in self.engines.items()}
            with open(self.persistence_path, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save engine registry state: {e}")

    def _load_state(self):
        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path, 'r') as f:
                    state = json.load(f)
                    for name, enabled in state.items():
                        if name not in self.engines:
                            self.engines[name] = EngineMetadata(name=name, tier=EngineTier.TIER_3_RAPTOR, enabled=enabled)
                        else:
                            self.engines[name].enabled = enabled
            except Exception as e:
                logger.error(f"Failed to load engine registry state: {e}")

logger = logging.getLogger("system-orchestrator")

class ManagedTask:
    """Represents a background task with lifecycle tracking, priority, and auto-restart."""
    def __init__(self, name: str, coro_func: Callable[[], Coroutine], restart_on_fail: bool = True, priority: int = 10):
        self.name = name
        self.coro_func = coro_func
        self.restart_on_fail = restart_on_fail
        self.priority = priority 
        self.task: Optional[asyncio.Task] = None
        self.failure_count = 0
        self.last_start_time = 0.0
        self.is_running = False
        self.is_paused = False

    async def _run_wrapper(self):
        self.is_running = True
        self.last_start_time = time.time()
        try:
            logger.info(f"🚀 Task '{self.name}' starting (P{self.priority})...")
            while True:
                # [Nexus Phase 5: Task 1 & 6] Dynamic ETL Pausing / Triage Force-Sleep
                from core.nexus.audit.triage import nexus_triage
                if self.priority > 5 and nexus_triage.current_backoff > 0.6:
                    self.is_paused = True
                    logger.warning(f"🛑 [NEXUS SHIELD] Auto-pausing background ETL '{self.name}' due to VPS pressure.")

                if self.is_paused:
                    await asyncio.sleep(5)
                    continue
                
                # [Phase 5: Task 8] Universal Analytics/Kafka Polling Throttling
                if self.priority <= 5 and nexus_triage.current_backoff > 0.4:
                    await asyncio.sleep(nexus_triage.current_backoff * 3.0)
                
                # [Phase 6: Task 10] Background Task Heartbeat Tracking
                from core.nexus.bootstrapper import nexus_boot
                nexus_boot.recovery.record_heartbeat(f"bg_task_{self.name}")

                await self.coro_func()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"🛑 Task '{self.name}' was cancelled.")
        except Exception as e:
            self.failure_count += 1
            logger.error(f"❌ Task '{self.name}' failed: {e}\n{traceback.format_exc()}")
            orchestrator.report_task_failure(self.name)
            if self.restart_on_fail:
                await asyncio.sleep(min(2 ** self.failure_count, 60))
                self.start()
        finally:
            self.is_running = False

    def start(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.is_paused = False
        self.task = asyncio.create_task(self._run_wrapper())

    def pause(self):
        if not self.is_paused:
            logger.info(f"💤 Task '{self.name}' entering sleep mode.")
            self.is_paused = True

    def resume(self):
        if self.is_paused:
            logger.info(f"☀️ Task '{self.name}' waking up.")
            self.is_paused = False

    def stop(self):
        if self.task:
            self.task.cancel()

class LoopWatchdog:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self.last_check_in = time.time()
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def check_in(self):
        self.last_check_in = time.time()

    def _watch_loop(self):
        logger.info("Watchdog Thread: Monitoring event loop health...")
        while self.is_running:
            time.sleep(1) 
            silence_duration = time.time() - self.last_check_in
            if silence_duration > 1.0:
                logger.warning(f"EVENT LOOP BLOCKED: {silence_duration:.2f}s!")
                if silence_duration > self.timeout:
                    import faulthandler
                    import sys
                    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
                    os._exit(1)

    def start(self):
        self.is_running = True
        self.last_check_in = time.time()
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

class PenaltyBoxManager:
    def __init__(self, error_threshold: int = 10, window_sec: int = 60, jail_sec: int = 600):
        self.error_threshold = error_threshold
        self.window_sec = window_sec
        self.jail_sec = jail_sec
        self.redis: Optional[Any] = None

    async def report_error(self, ip: str):
        if not self.redis: return
        try:
            key = f"penalty:errors:{ip}"
            count = await self.redis.incr(key)
            if count == 1: await self.redis.expire(key, self.window_sec)
            if count >= self.error_threshold:
                await self.redis.set(f"penalty:jail:{ip}", "1", ex=self.jail_sec)
        except: pass

    async def is_jailed(self, ip: str) -> bool:
        if not self.redis: return False
        try:
            return (await self.redis.exists(f"penalty:jail:{ip}")) > 0
        except:
            return False

class SystemOrchestrator:
    def __init__(self):
        self.tasks: Dict[str, ManagedTask] = {}
        self.engine_registry = EngineRegistry() 
        self.start_time = time.time()
        self.is_shutting_down = False
        self._maintenance_mode = False
        self._kill_switch = False
        self.watchdog = LoopWatchdog()
        self.penalty_box = PenaltyBoxManager()
        self.total_failures = 0
        self.last_panic_reset = time.time()

        self.active_requests = 0
        self.active_user_ids: Set[str] = set()
        self.last_request_time = time.time()
        self.is_sleeping = False
        self.activity_level = "IDLE"
        
        # [Task 24.1] RPM tracking
        self.request_timestamps: List[float] = []
        self._last_rpm = 0

    def get_rpm(self) -> Dict[str, Any]:
        """[Task 24.1/24.3] Calculate RPM and velocity trend."""
        now = time.time()
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
        current_rpm = len(self.request_timestamps)
        
        delta = current_rpm - self._last_rpm
        self._last_rpm = current_rpm
        
        return {
            "current_rpm": current_rpm,
            "rpm_delta": delta,
            "trend": "INCREASING" if delta > 5 else "STABLE" if abs(delta) <= 5 else "DECREASING"
        }

    def report_task_failure(self, task_name: str):
        self.total_failures += 1
        now = time.time()
        if now - self.last_panic_reset > 3600:
            self.total_failures = 1
            self.last_panic_reset = now
        if self.total_failures > 50:
            os._exit(1)

    def report_request(self, user_id: Optional[str] = None):
        self.active_requests += 1
        self.request_timestamps.append(time.time()) # [Task 24.1]
        if user_id: self.active_user_ids.add(user_id)
        self.last_request_time = time.time()
        self._update_activity_level()
        if self.is_sleeping: asyncio.create_task(self.wakeup())

    def _update_activity_level(self):
        count = self.active_requests
        if count == 0: self.activity_level = "IDLE"
        elif count < 5: self.activity_level = "LITE"
        elif count < 20: self.activity_level = "ACTIVE"
        else: self.activity_level = "BURST"

    def report_request_end(self, user_id: Optional[str] = None):
        self.active_requests = max(0, self.active_requests - 1)
        self._update_activity_level()

    async def wakeup(self):
        if not self.is_sleeping: return
        self.is_sleeping = False
        for task in self.tasks.values():
            if task.priority >= 2: task.resume()

    async def _sleep_monitor_loop(self):
        while not self.is_shutting_down:
            await asyncio.sleep(60)
            idle_time = time.time() - self.last_request_time
            if not self.is_sleeping and self.active_requests == 0 and idle_time > 300:
                self.is_sleeping = True
                for task in self.tasks.values():
                    if task.priority >= 2: task.pause()

    async def _worker_memory_watchdog(self):
        RSS_LIMIT_MB = 500 
        import psutil
        import signal
        while not self.is_shutting_down:
            await asyncio.sleep(30)
            try:
                process = psutil.Process()
                rss_mb = process.memory_info().rss / (1024 * 1024)
                if rss_mb > RSS_LIMIT_MB:
                    os.kill(os.getpid(), signal.SIGTERM)
                    break
            except: pass

    async def _zombie_task_reaper(self):
        """[Task 77] Scans managed tasks for stagnation or excessive failures."""
        while not self.is_shutting_down:
            await asyncio.sleep(300) # Check every 5 mins
            for name, task in list(self.tasks.items()):
                if task.failure_count > 10:
                    logger.critical(f"🧟 [NEXUS:REAPER] Task '{name}' has {task.failure_count} failures. FORCING STOP.")
                    task.stop()
                    # Mark as zombie for remediation
                    self._mark_zombie(name)

    def _mark_zombie(self, name: str):
        # Placeholder for reporting to external monitor
        pass

    async def _zombie_connection_reaper(self):
        """[Phase 5: Task 5 & 9] Kill idle SQLAlchemy pools and force JIT GC."""
        while not self.is_shutting_down:
            await asyncio.sleep(120)
            try:
                from database.session import engine
                engine.dispose()
                import gc; gc.collect()
                logger.info("🧹 [NEXUS SHIELD] Reaped zombie DB connections & Forced GC sweep.")
            except: pass

    async def _ghost_mode_monitor(self):
        """[Phase 5: Task 2 & Task 10] Track DB/L2 Health & Trigger Ghost Mode."""
        from core.nexus.bootstrapper import nexus_boot, SystemState
        from services.multi_layer_cache import multi_layer_cache
        from database.session import AsyncSessionLocal
        from sqlalchemy import text
        while not self.is_shutting_down:
            await asyncio.sleep(15)
            # Check DB health
            db_ok = True
            try:
                async with AsyncSessionLocal() as session:
                    await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=3.0)
            except Exception as e:
                db_ok = False
            
            # Check Redis Health
            try:
                from core.providers import ServiceStatus
                cache_status = await multi_layer_cache.health_check()
                redis_ok = cache_status == ServiceStatus.HEALTHY
            except:
                redis_ok = False
            
            # State transitions
            severed_state = getattr(SystemState, "SEVERED", None)
            degraded_state = getattr(SystemState, "DEGRADED", None)
            ready_state = getattr(SystemState, "READY", None)

            if not db_ok and not redis_ok:
                if severed_state is not None and getattr(nexus_boot, 'state', None) != severed_state:
                    logger.critical("👻 [NEXUS SHIELD] DB & Redis DEAD. Entering GHOST MODE (SEVERED).")
                    nexus_boot.state = severed_state
            elif not db_ok or not redis_ok:
                if degraded_state is not None and getattr(nexus_boot, 'state', None) != degraded_state:
                    logger.warning("⚠️ [NEXUS SHIELD] Partial Outage. Entering DEGRADED mode.")
                    nexus_boot.state = degraded_state
            else:
                if ready_state is not None and getattr(nexus_boot, 'state', None) in [severed_state, degraded_state]:
                    logger.info("☀️ [NEXUS SHIELD] Outage Resolved. Restoring READY state.")
                    nexus_boot.state = ready_state
            
            # [Task 10] OS Latch File to prevent Docker Restart Loops
            try:
                with open("/tmp/nexus_healthy.lock", "w") as f: f.write(str(time.time()))
            except: pass

    async def _watchdog_checkin_loop(self):
        while not self.is_shutting_down:
            self.watchdog.check_in()
            await asyncio.sleep(2)

    def register_task(self, name: str, coro_func: Callable[[], Coroutine], restart_on_fail: bool = True, priority: int = 10):
        self.tasks[name] = ManagedTask(name, coro_func, restart_on_fail, priority)

    async def bootstrap(self):
        self.watchdog.start()
        asyncio.create_task(self._watchdog_checkin_loop())
        asyncio.create_task(self._sleep_monitor_loop())
        asyncio.create_task(self._worker_memory_watchdog())
        asyncio.create_task(self._zombie_task_reaper())
        asyncio.create_task(self._zombie_connection_reaper())
        asyncio.create_task(self._ghost_mode_monitor())
        from services.multi_layer_cache import multi_layer_cache
        self.penalty_box.redis = multi_layer_cache.redis
        sorted_tasks = sorted(self.tasks.values(), key=lambda x: x.priority)
        for task in sorted_tasks:
            if task.priority < 2:
                task.start()
                await asyncio.sleep(0.1)

    async def shutdown(self, timeout: float = 10.0):
        if self.is_shutting_down: return
        self.is_shutting_down = True
        self.watchdog.stop()
        for task in self.tasks.items(): task[1].stop()
        pending = [t.task for t in self.tasks.values() if t.task and not t.task.done()]
        if pending:
            try: await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=timeout)
            except: pass

    def get_health_report(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": time.time() - self.start_time,
            "tasks": {
                name: {"is_running": t.is_running, "failure_count": t.failure_count, "priority": t.priority}
                for name, t in self.tasks.items()
            }
        }

orchestrator = SystemOrchestrator()
