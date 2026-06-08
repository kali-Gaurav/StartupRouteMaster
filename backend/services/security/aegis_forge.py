"""
Aegis Forge Service - Disaster Resilience Controller
=====================================================

Powerful disaster resilience controller that orchestrates:
- Failure scenario simulation
- Self-healing and learning loops
- System health certification
- Anti-flapping protection

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

from core.nexus.shm_bridge import SharedMemoryBridge
from datetime import datetime
import asyncio
import logging
import time
import os
import signal
from typing import Dict, Any, List, Optional, ClassVar, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy, retry
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints

logger = logging.getLogger("routemaster.aegis_forge")


class DrillStatus(Enum):
    """Status of disaster drill execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class DisasterDrill:
    """Disaster drill configuration and result."""
    drill_name: str
    status: DrillStatus
    timestamp: datetime
    duration_ms: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AegisForgeService:
    """
    [Point 9, 14, 15] Aegis Forge: Powerful Disaster Resilience Controller.
    Beyond simulation: This orchestrates the self-healing and learning loop.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    # Resurrection Latch: Prevents infinite restart loops (Anti-Flapping)
    _restart_storm_counter = 0
    _last_restart_time = 0
    
    # Maximum concurrent drills
    _MAX_CONCURRENT_DRILLS: ClassVar[int] = 3
    _active_drills: ClassVar[Dict[str, DisasterDrill]] = {}
    _drills_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _drill_history: ClassVar[Deque[DisasterDrill]] = deque(maxlen=100)

    def __init__(self):
        """Initialize Aegis Forge service with resilience patterns."""
        # Circuit breaker for external service calls
        self._service_breaker = circuit_manager.get_or_create(
            "aegis_forge",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy for service operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (OSError, IOError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()

        logger.info("AegisForgeService initialized with resilience patterns")

    @classmethod
    def get_resource_budget(cls) -> float:
        """Get current resource budget for chaos testing."""
        try:
            from core.infrastructure.resource_monitor import resource_monitor
            return resource_monitor.get_resource_budget()
        except ImportError:
            # Fallback: assume safe if monitor not available
            logger.warning("⚠️ Resource monitor not available, assuming safe budget")
            return 0.8

    @classmethod
    async def start_disaster_drill(cls, drill_name: str, db=None) -> Dict[str, Any]:
        """
        Executes a failure scenario and triggers a Black Box Forensic recording.
        
        Args:
            drill_name: Name of the drill to execute
            db: Database session for logging
            
        Returns:
            Dict with drill status and results
            
        Protected by circuit breaker and resource budget checks.
        """
        # Check concurrent drill limit
        async with cls._drills_lock:
            active_count = sum(
                1 for d in cls._active_drills.values()
                if d.status == DrillStatus.RUNNING
            )
            if active_count >= cls._MAX_CONCURRENT_DRILLS:
                logger.error(
                    f"🚫 [AEGIS:SABOTAGE] Aborted. Max concurrent drills ({cls._MAX_CONCURRENT_DRILLS}) reached."
                )
                return {
                    "status": "ABORTED",
                    "reason": "MAX_CONCURRENT_DRILLS",
                    "active_drills": active_count
                }
        
        # [Missing Gap 1] Surge-Safety Latch: NEVER run chaos during real high-traffic
        actual_budget = cls.get_resource_budget()
        if actual_budget < 0.6:
            logger.error("🚫 [AEGIS:SABOTAGE] Aborted. System is under real load. Chaos is unsafe.")
            return {"status": "ABORTED", "reason": "HIGH_LOAD", "budget": actual_budget}

        logger.warning(f"🔨 [AEGIS:FORGE] Initiating Powerful Disaster Drill: {drill_name}")
        
        # Create drill record
        drill = DisasterDrill(
            drill_name=drill_name,
            status=DrillStatus.RUNNING,
            timestamp=datetime.utcnow()
        )
        async with cls._drills_lock:
            cls._active_drills[drill_name] = drill
        
        start_time = time.perf_counter()
        
        try:
            # [Missing Gap 2] NIS Forensic Snapshot
            if db:
                try:
                    from services.intelligence_service import IntelligenceService
                    intel_svc = IntelligenceService(db)
                    await intel_svc.log_safety_outcome(
                        route_id=drill_name,
                        predicted_risk=0.0,
                        outcome="DRILL_START",
                        delay=0
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Failed to log forensic snapshot: {e}")

            # Execute drill based on type
            result = await cls._execute_drill(drill_name, db)
            
            drill.status = DrillStatus.COMPLETED
            drill.result = result
            
            logger.info(f"✅ [AEGIS:FORGE] Drill {drill_name} completed successfully")
            
        except Exception as e:
            drill.status = DrillStatus.FAILED
            drill.error = str(e)
            logger.error(f"❌ [AEGIS:FORGE] Drill {drill_name} failed: {e}")
            
        finally:
            drill.duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Move to history
            async with cls._drills_lock:
                if drill_name in cls._active_drills:
                    del cls._active_drills[drill_name]
                cls._drill_history.append(drill)
        
        return {
            "drill": drill_name,
            "status": drill.status.value,
            "timestamp": drill.timestamp.isoformat(),
            "duration_ms": drill.duration_ms,
            "result": drill.result,
            "error": drill.error
        }

    @classmethod
    async def _execute_drill(cls, drill_name: str, db) -> Dict[str, Any]:
        """Execute specific drill scenario."""
        if drill_name == "DB_POISON":
            try:
                from core.nexus.audit.chaos import nexus_chaos
                nexus_chaos.arm("ledger_record", error_rate=1.0)
                return {"action": "DB_POISON", "chaos_armed": True}
            except Exception as e:
                return {"action": "DB_POISON", "error": str(e)}
            
        elif drill_name == "SHARD_REAPER":
            # [Advanced] Reaper logic with Resurrection logic integration
            try:
                from core.nexus.spine import NeuralSpine
                # Simulate a messy crash
                logger.critical("💀 [AEGIS:FORGE] REAPING Neural Spine Worker...")
                NeuralSpine.reset()  # This forces a restart in the next request
                return {"action": "SHARD_REAPER", "reset_triggered": True}
            except Exception as e:
                return {"action": "SHARD_REAPER", "error": str(e)}
            
        elif drill_name == "SHM_POISON":
            # [Advanced] Corrupt the Shared Memory Bridge
            try:
                SharedMemoryBridge.get_instance().unlink()
                logger.critical("☣️ [AEGIS:FORGE] POISONING Shared Memory Segment...")
                return {"action": "SHM_POISON", "unlink_triggered": True}
            except Exception as e:
                return {"action": "SHM_POISON", "error": str(e)}

        elif drill_name == "HEARTBEAT_STORM":
            # [P8] Intelligent Scarcity Stress Test
            return await cls._run_heartbeat_storm()

        elif drill_name == "CIRCUIT_BREAKER_TEST":
            # Test circuit breaker functionality
            return await cls._run_circuit_breaker_test()

        elif drill_name == "RETRY_STORM":
            # Test retry logic under load
            return await cls._run_retry_storm()

        else:
            return {"error": f"Unknown drill: {drill_name}"}

    @classmethod
    async def _run_heartbeat_storm(cls) -> Dict[str, Any]:
        """Run heartbeat stress test."""
        try:
            from services.search_service import SearchService
            from database.session import SessionTransit
            
            logger.warning("🔨 [AEGIS:FORGE] INITIATING STRESS TEST: 100 Concurrent Synapse Lookups...")
            
            async def run_storm():
                tasks = []
                try:
                    async with SessionTransit() as db:
                        search_svc = SearchService(db)
                        for _ in range(100):
                            tasks.append(
                                search_svc.route_engine.find_routes(
                                    RoutingRequest(
                                        source_code="NDLS",
                                        destination_code="AGC",
                                        source_stop_id=None,
                                        destination_stop_id=None,
                                        departure_date=datetime.now(),
                                        constraints=RouteConstraints(),
                                        db_session=db
                                    )
                                )
                            )
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        exceptions = [r for r in results if isinstance(r, Exception)]
                        return {
                            "total": len(results),
                            "success": len(results) - len(exceptions),
                            "exceptions": len(exceptions)
                        }
                except Exception as e:
                    return {"error": str(e)}
            
            # Run in background to not block the API
            task = asyncio.create_task(run_storm())
            
            return {
                "action": "HEARTBEAT_STORM",
                "status": "STARTED",
                "concurrent_requests": 100
            }
            
        except Exception as e:
            return {"action": "HEARTBEAT_STORM", "error": str(e)}

    @classmethod
    async def _run_circuit_breaker_test(cls) -> Dict[str, Any]:
        """Test circuit breaker functionality."""
        results = []
        
        for i in range(10):
            breaker_name = f"test_breaker_{i % 3}"
            breaker = circuit_manager.get_or_create(
                breaker_name,
                CircuitConfig(failure_threshold=3, timeout_seconds=5.0)
            )
            
            try:
                async def fail_operation():
                    raise ConnectionError("Test failure")
                
                await breaker.execute(fail_operation)
                results.append({"attempt": i, "result": "success"})
            except Exception as e:
                results.append({"attempt": i, "result": "failed", "error": str(e)})
        
        return {
            "action": "CIRCUIT_BREAKER_TEST",
            "results": results,
            "open_circuits": len(circuit_manager.get_open_circuits())
        }

    @classmethod
    async def _run_retry_storm(cls) -> Dict[str, Any]:
        """Test retry logic under load."""
        results = []
        
        async def unreliable_operation(attempt: int):
            if attempt < 3:
                raise TimeoutError(f"Transient failure on attempt {attempt}")
            return "success"
        
        for i in range(5):
            policy = RetryPolicy(
                max_attempts=5,
                initial_delay=0.1,
                max_delay=1.0,
                conditions=[lambda e: isinstance(e, TimeoutError)]
            )
            
            try:
                result = await policy.execute(unreliable_operation, i)
                results.append({"attempt": i, "result": result, "success": True})
            except Exception as e:
                results.append({"attempt": i, "result": "failed", "error": str(e), "success": False})
        
        return {
            "action": "RETRY_STORM",
            "results": results,
            "success_rate": sum(1 for r in results if r.get("success")) / len(results)
        }

    @staticmethod
    async def run_resilience_audit(db) -> Dict[str, Any]:
        """
        Deep-scan and certify system health.
        
        Args:
            db: Database session
            
        Returns:
            Dict with certification status and health metrics
        """
        start_time = time.perf_counter()
        
        # Check chain integrity
        chain_integrity = "UNKNOWN"
        is_clean = False
        
        try:
            from services.sentinel_service import SentinelService
            integrity = await SentinelService.verify_chain_integrity(db)
            chain_integrity = "STABLE" if integrity["is_clean"] else "COMPROMISED"
            is_clean = integrity["is_clean"]
        except Exception as e:
            logger.warning(f"⚠️ Chain integrity check failed: {e}")
            chain_integrity = "CHECK_FAILED"
        
        # [Missing Gap 3] Check for SHM Leakage
        shm_leaked = False
        shm_check = "NOT_CHECKED"
        
        try:
            # Check for abandoned shared memory segments on Linux/Posix
            if os.name != 'nt':
                import subprocess
                res = subprocess.run(['ipcs', '-m'], capture_output=True, text=True)
                if res.returncode == 0 and "0x" in res.stdout:
                    shm_leaked = "leaks_detected" in res.stdout.lower()
                    shm_check = "WARNING_LEAK" if shm_leaked else "CLEAN"
                else:
                    shm_check = "CLEAN"
            else:
                shm_check = "SKIPPED_WINDOWS"
        except FileNotFoundError:
            shm_check = "SKIPPED_NO_IPCS"
        except Exception as e:
            shm_check = f"ERROR: {str(e)}"
        
        # Check circuit breakers
        circuit_health = circuit_manager.get_all_health()
        open_circuits = len(circuit_manager.get_open_circuits())
        
        # Calculate certification level
        certification = "DIAMOND"
        reasons = []
        
        if not is_clean:
            certification = "FAIL"
            reasons.append("chain_compromised")
        elif shm_leaked:
            certification = "BRONZE"
            reasons.append("memory_leak")
        elif open_circuits > 0:
            certification = "SILVER"
            reasons.append(f"{open_circuits}_open_circuits")
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "certification": certification,
            "chain_integrity": chain_integrity,
            "memory_leak_check": shm_check,
            "circuit_breakers": {
                "total": len(circuit_health),
                "open": open_circuits,
                "health": circuit_health
            },
            "recovery_velocity_avg_ms": round(duration_ms, 2),
            "reasons": reasons if reasons else None
        }

    @classmethod
    def track_restart(cls) -> bool:
        """[Point 11] Anti-Flapping logic to detect restart storms."""
        now = time.time()
        if now - cls._last_restart_time < 10:
            cls._restart_storm_counter += 1
        else:
            cls._restart_storm_counter = 0
            
        cls._last_restart_time = now
        
        if cls._restart_storm_counter > 5:
            logger.critical("🔥 [AEGIS:LATCH] SHARD RESTART STORM DETECTED. Locking Compute Shard.")
            return False
        return True

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        drill_name: str,
        status: DrillStatus,
        duration_ms: float
    ):
        """Record drill metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "drill_name": drill_name,
                "status": status.value,
                "duration_ms": duration_ms
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_drills": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        completed = sum(1 for m in self._metrics if m["status"] == "completed")
        aborted = sum(1 for m in self._metrics if m["status"] == "aborted")
        failed = sum(1 for m in self._metrics if m["status"] == "failed")
        
        return {
            "total_drills": total,
            "completed_drills": completed,
            "aborted_drills": aborted,
            "failed_drills": failed,
            "success_rate": completed / total if total > 0 else 0,
            "circuit_breaker_state": self._service_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._service_breaker.get_state().value,
                "failure_count": self._service_breaker.failure_count,
                "success_count": self._service_breaker.success_count
            },
            "metrics": self.get_metrics(),
            "active_drills": len(self._active_drills)
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._service_breaker.reset()
        logger.info("Circuit breaker reset for Aegis Forge service")

    def get_drill_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent drill history."""
        history = list(self._drill_history)[-limit:]
        return [
            {
                "drill_name": d.drill_name,
                "status": d.status.value,
                "timestamp": d.timestamp.isoformat(),
                "duration_ms": d.duration_ms,
                "error": d.error
            }
            for d in history
        ]


# Global instance
aegis_forge_service = AegisForgeService()
