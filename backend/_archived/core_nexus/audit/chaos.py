import asyncio
import random
import logging
import time
import functools
from typing import Dict, Any, List, Optional
from utils.integrity import integrity_engine

logger = logging.getLogger("nexus.chaos")

class ChaosMesh:
    """
    [Task 25.1] Nexus Chaos Fabric.
    A central registry for programmatically arming 'Chaos Traps' across the fiber.
    Supports stochastic jitter (Uniform/Gaussian) to test resilience limits.
    """
    
    def __init__(self):
        self._traps: Dict[str, Dict[str, Any]] = {}
        self._active = True
        
    def arm(self, name: str, base_delay: float = 0.0, jitter: float = 0.0, error_rate: float = 0.0):
        """[Task 25.12] Registers or updates a failure mode."""
        self._traps[name] = {
            "base": base_delay,
            "jitter": jitter,
            "error_rate": error_rate,
            "armed": True
        }
        logger.warning(f"🛡️ [CHAOS] Trap ARMED: '{name}' (Delay: {base_delay}s +-{jitter}s, Fail: {error_rate*100}%)")
        integrity_engine.record("chaos_mesh", "TRAP_ARMED", severity="WARNING", details={"trap": name, "params": self._traps[name]})

    def disarm(self, name: str):
        """Disable a specific failure mode."""
        if name in self._traps:
            self._traps[name]["armed"] = False
            logger.info(f"🛡️ [CHAOS] Trap DISARMED: '{name}'")
            integrity_engine.record("chaos_mesh", "TRAP_DISARMED", severity="INFO", details={"trap": name})

    async def apply_trap(self, name: str):
        """[Task 25.2/25.3] Executes the latency/failure logic for an armed trap (Async)."""
        # Fast path: skip thread pool overhead if no trap is armed (99% of prod requests)
        trap = self._traps.get(name)
        if not (trap and trap.get("armed")):
            return
        await asyncio.to_thread(self.apply_trap_sync, name)

    def apply_trap_sync(self, name: str):
        """[Task 25.4] Executes the latency/failure logic for an armed trap (Sync)."""
        trap = self._traps.get(name)
        if not (trap and trap["armed"]):
            return

        # 1. Error Rate (Simulated Failure)
        if trap["error_rate"] > 0:
             if random.random() < trap["error_rate"]:
                  logger.error(f"💣 [CHAOS:FAILURE] Injecting Fault: '{name}'")
                  integrity_engine.record("chaos_mesh", "FAULT_INJECTED", severity="CRITICAL", details={"trap": name})
                  raise RuntimeError(f"ChaosMesh: Forced failure for trap '{name}'")

        # 2. Latency (Stochastic Jitter)
        delay = trap["base"]
        if trap["jitter"] > 0:
             delay += random.uniform(-trap["jitter"], trap["jitter"])
        
        if delay > 0:
             logger.debug(f"⏳ [CHAOS:LATENCY] Injecting Delay: '{name}' ({delay:.3f}s)")
             time.sleep(max(0, delay))
    
    def is_severed(self, name: str) -> bool:
        """[Task 26.1] Check if a specific service/trap is considered severed."""
        trap = self._traps.get(name)
        return trap is not None and trap.get("armed", False) and trap.get("error_rate", 0) >= 1.0

    @property
    def active_traps(self) -> Dict[str, Any]:
        """[Task 25.14] Dynamic registry of currently armed failure modes."""
        return {name: params for name, params in self._traps.items() if params.get("armed")}

    def get_all_traps(self) -> Dict[str, Any]:
        return self.active_traps

    async def start_creeping_slowdown(self, name: str, rate: float = 0.01, interval: int = 10):
        """
        [Task 25.11] Gradually increases base_delay for a specific trap.
        Simulates a 'Sinking system' where latency climbs over time.
        """
        if name not in self._traps:
            self.arm(name, base_delay=0.1)
            
        logger.warning(f"🧟 [CHAOS] CREEPING SLOWDOWN initiated for '{name}' (Rate: {rate}s every {interval}s)")
        integrity_engine.record("chaos_mesh", "CREEPING_SLOWDOWN_START", severity="WARNING", details={"trap": name, "rate": rate})
        
        while self._traps.get(name, {}).get("armed"):
            self._traps[name]["base"] += rate
            if self._traps[name]["base"] > 5.0: # Cap at 5 seconds delay
                 logger.error(f"🧟 [CHAOS] CREEPING SLOWDOWN hit CAP (5s) for '{name}'. Stopping creep.")
                 break
            await asyncio.sleep(interval)

def chaos_trap(trap_name: str):
    """
    [Task 25.2] Reusable async decorator for fault injection.
    Usage:
        @chaos_trap("search_v3")
        async def perform_search(...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Apply chaos before execution
            await nexus_chaos.apply_trap(trap_name)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Global Singleton
nexus_chaos = ChaosMesh()
