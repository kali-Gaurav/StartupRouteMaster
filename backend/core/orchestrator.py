import asyncio
import logging
import time
import traceback
import random
import threading
from datetime import datetime
from typing import Dict, Any, List, Callable, Coroutine, Optional

logger = logging.getLogger("system-orchestrator")

class ManagedTask:
    """Represents a background task with lifecycle tracking, priority, and auto-restart."""
    def __init__(self, name: str, coro_func: Callable[[], Coroutine], restart_on_fail: bool = True, priority: int = 10):
        self.name = name
        self.coro_func = coro_func
        self.restart_on_fail = restart_on_fail
        self.priority = priority # Lower is higher priority
        self.task: Optional[asyncio.Task] = None
        self.failure_count = 0
        self.last_start_time = 0.0
        self.is_running = False

    async def _run_wrapper(self):
        self.is_running = True
        self.last_start_time = time.time()
        try:
            logger.info(f"🚀 Task '{self.name}' starting (P{self.priority})...")
            await self.coro_func()
        except asyncio.CancelledError:
            logger.info(f"🛑 Task '{self.name}' was cancelled.")
        except Exception as e:
            self.failure_count += 1
            logger.error(f"❌ Task '{self.name}' failed: {e}\n{traceback.format_exc()}")
            if self.restart_on_fail:
                wait_time = min(2 ** self.failure_count, 60) # Exponential backoff
                logger.info(f"🔄 Task '{self.name}' will restart in {wait_time}s...")
                await asyncio.sleep(wait_time)
                self.start()
        finally:
            self.is_running = False

    def start(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = asyncio.create_task(self._run_wrapper())

    def stop(self):
        if self.task:
            self.task.cancel()

class LoopWatchdog:
    """
    Subtask 1.15: Loop Deadlock Watchdog.
    Runs in a dedicated OS thread. Monitors the event loop health.
    If the loop is blocked for > 30s, it indicates a hard deadlock.
    """
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.last_check_in = time.time()
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def check_in(self):
        self.last_check_in = time.time()

    def _watch_loop(self):
        logger.info("🛡️ Watchdog Thread: Monitoring event loop health...")
        while self.is_running:
            time.sleep(5)
            silence_duration = time.time() - self.last_check_in
            if silence_duration > self.timeout:
                logger.critical(
                    f"💀 EVENT LOOP DEADLOCK DETECTED! No check-in for {silence_duration:.2f}s. "
                    "FORCING SYSTEM RESTART..."
                )
                # Task 20.2: Force process exit to trigger hard-restart loop in start.sh
                import os
                os._exit(1)

    def start(self):
        self.is_running = True
        self.last_check_in = time.time()
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

class SystemOrchestrator:
    """
    Advanced System Orchestrator.
    [Subtask 1.10] Handles 24/7 reliability with staggered Jittered Bootstrap.
    [Subtask 1.12] Maintenance Mode Management.
    [Subtask 1.15] Loop Watchdog Integration.
    [Subtask 1.17] Emergency Kill Switch.
    """
    def __init__(self):
        self.tasks: Dict[str, ManagedTask] = {}
        self.start_time = time.time()
        self.is_shutting_down = False
        self._maintenance_mode = False
        self._kill_switch = False
        self.watchdog = LoopWatchdog()

    async def set_kill_switch(self, active: bool):
        self._kill_switch = active
        from services.multi_layer_cache import multi_layer_cache
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.set("system:kill_switch", "1" if active else "0")
        logger.critical(f"⚠️ EMERGENCY KILL SWITCH {'ACTIVATED' if active else 'DEACTIVATED'}!")

    async def is_kill_switch_active(self) -> bool:
        from services.multi_layer_cache import multi_layer_cache
        if multi_layer_cache.redis:
            val = await multi_layer_cache.redis.get("system:kill_switch")
            return val == b"1" or val == "1"
        return self._kill_switch

    async def _watchdog_checkin_loop(self):
        """Async task that periodically pings the watchdog."""
        while not self.is_shutting_down:
            self.watchdog.check_in()
            await asyncio.sleep(2)

    async def set_maintenance_mode(self, enabled: bool):
        self._maintenance_mode = enabled
        from services.multi_layer_cache import multi_layer_cache
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.set("system:maintenance_mode", "1" if enabled else "0")
        logger.warning(f"🛠️ Maintenance Mode {'ENABLED' if enabled else 'DISABLED'}")

    async def is_in_maintenance(self) -> bool:
        from services.multi_layer_cache import multi_layer_cache
        if multi_layer_cache.redis:
            val = await multi_layer_cache.redis.get("system:maintenance_mode")
            return val == b"1" or val == "1"
        return self._maintenance_mode

    def register_task(self, name: str, coro_func: Callable[[], Coroutine], restart_on_fail: bool = True, priority: int = 10):
        """Registers a background service."""
        self.tasks[name] = ManagedTask(name, coro_func, restart_on_fail, priority)

    async def bootstrap(self):
        """
        Subtask 1.10: Staggered Jittered Bootstrap.
        Starts tasks by priority with small random delays to avoid CPU spikes.
        """
        logger.info("🛠️ System Orchestrator: Beginning staggered bootstrap...")
        
        # [1.15] Start Watchdog
        self.watchdog.start()
        asyncio.create_task(self._watchdog_checkin_loop())
        
        # Sort tasks by priority
        sorted_tasks = sorted(self.tasks.values(), key=lambda x: x.priority)
        
        for task in sorted_tasks:
            if self.is_shutting_down: break
            
            # Add jitter (0.1s to 0.5s)
            jitter = random.uniform(0.1, 0.5)
            await asyncio.sleep(jitter)
            
            task.start()
            
        logger.info("✅ All background services orchestrated.")

    async def shutdown(self):
        """Graceful shutdown of all managed services."""
        self.is_shutting_down = True
        self.watchdog.stop()
        logger.info("🔌 System Orchestrator: Beginning graceful shutdown...")
        for task in self.tasks.values():
            task.stop()
        
        # Wait for all tasks to finish cancellation
        pending = [t.task for t in self.tasks.values() if t.task]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        logger.info("🛑 All services stopped.")

    def get_health_report(self) -> Dict[str, Any]:
        """Returns the status of all managed background tasks."""
        return {
            "uptime_seconds": time.time() - self.start_time,
            "tasks": {
                name: {
                    "is_running": t.is_running,
                    "failure_count": t.failure_count,
                    "priority": t.priority,
                    "last_start": datetime.fromtimestamp(t.last_start_time).isoformat() if t.last_start_time > 0 else None
                }
                for name, t in self.tasks.items()
            }
        }

# Global Orchestrator Instance
orchestrator = SystemOrchestrator()
