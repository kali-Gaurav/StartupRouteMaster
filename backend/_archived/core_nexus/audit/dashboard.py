import logging
import time
import os
from typing import Dict, Any, List
from core.nexus.bootstrapper import nexus_boot
from core.nexus.state import SystemState
from core.resilience.core import CircuitBreaker
from core.infrastructure.resource_monitor import resource_monitor

logger = logging.getLogger("nexus.audit.dashboard")

class NexusAuditDashboard:
    """[Task 22] Master High-Integrity Dashboard.
    Provides real-time visualization data for:
    1. Node Recovery Events (Auto-Recovery Sentinel)
    2. Multi-Layer Circuit Breakers (Resilience Layer)
    3. VPS Hygiene (CPU, RAM, Disk)
    4. Database Lock density (Task 23)
    """
    
    @staticmethod
    def _get_db_watchdog_stats() -> Dict[str, Any]:
        """[Task 23] Fetch database lock metrics."""
        try:
            from core.nexus.database.watchdog import database_watchdog
            return database_watchdog.get_stats()
        except ImportError:
            return {"status": "DISABLED"}

    @staticmethod
    def _get_chaos_mesh_stats() -> Dict[str, Any]:
        """[Task 25.14] Fetch active chaos traps."""
        try:
             from core.nexus.audit.chaos import nexus_chaos
             return nexus_chaos.get_all_traps()
        except: return {}

    @staticmethod
    def get_system_vitals() -> Dict[str, Any]:
        """Collects real-time integrity metrics from the entire Nexus Fiber."""
        recovery = nexus_boot.recovery
        stats = resource_monitor.get_stats()
        
        vitals = {
            "timestamp": time.time(),
            "global_state": nexus_boot.state.value,
            "vps_hygiene": {
                "cpu_percent": stats.get("cpu_percent", 0),
                "ram_percent": stats.get("ram_percent", 0),
                "process_rss_mb": round(stats.get("process_rss_mb", 0), 2),
                "load_shedding_active": stats.get("state") != "HEALTHY"
            },
            "recovery_sentinel": {
                "active": recovery._monitoring_task is not None and not recovery._monitoring_task.done(),
                "restart_counts": recovery._restart_counts,
                "last_heartbeats": {
                    name: round(time.time() - ts, 1) if ts > 0 else -1
                    for name, ts in recovery._last_heartbeat.items()
                }
            },
            "circuit_breakers": CircuitBreaker.get_all_statuses(),
            "database_locks": NexusAuditDashboard._get_db_watchdog_stats(),
            "memory_leaks": nexus_boot.profiler.get_stats(),
            "chaos_mesh": NexusAuditDashboard._get_chaos_mesh_stats(),
            "nodes": {
                name: {
                    "status": node.status.name,
                    "critical": node.critical,
                    "dependencies": node.dependencies
                } for name, node in nexus_boot.nodes.items()
            }
        }
        return vitals

    @staticmethod
    def get_triage_report() -> str:
        """Generates a human-readable high-integrity triage report."""
        vitals = NexusAuditDashboard.get_system_vitals()
        report = []
        report.append(f"🛡️ [NEXUS:TRIAGE] State: {vitals['global_state']}")
        report.append(f"💻 VPS: CPU {vitals['vps_hygiene']['cpu_percent']}% | RAM {vitals['vps_hygiene']['ram_percent']}%")
        
        # DB Locks
        db_locks = vitals['database_locks']
        if db_locks.get('status') != "HEALTHY" and db_locks.get('status') != "DISABLED":
             report.append(f"🗄️ DB_LOCK_PRESSURE: {db_locks.get('status')} (Density: {db_locks.get('lock_density_epm')} epm)")

        # Memory Leaks
        leaks = vitals['memory_leaks']
        if leaks.get('leak_incidents', 0) > 0:
             report.append(f"🧠 MEMORY_LEAK_ALERT: {leaks.get('leak_incidents')} incidents detected!")

        # Circuits
        tripped = [c['name'] for c in vitals['circuit_breakers'] if c['state'] != "CLOSED"]
        if tripped:
            report.append(f"🚨 TRIPPED CIRCUITS: {', '.join(tripped)}")
        else:
            report.append("✅ ALL CIRCUITS CLOSED (Healthy)")
            
        # Node Restarts
        restarts = {n: count for n, count in vitals['recovery_sentinel']['restart_counts'].items() if count > 0}
        if restarts:
            report.append(f"🔄 RECOVERY EVENTS: {restarts}")
        
        return "\n".join(report)

    @staticmethod
    def perform_deep_audit() -> bool:
        """[Audit Protocol] Performs deep integrity sweep and logs anomalies."""
        logger.info("🛡️ [NEXUS:AUDIT] Initiating Real-Time Deep Audit (Task 23)...")
        vitals = NexusAuditDashboard.get_system_vitals()
        
        # 1. Check for zombie nodes
        for name, elapsed in vitals['recovery_sentinel']['last_heartbeats'].items():
            if elapsed > 120: # 2 minutes
                logger.warning(f"⚠️ AUDIT WARNING: Node '{name}' heartbeat stale ({elapsed}s).")
                
        # 2. Check for critical fails
        if vitals['global_state'] == SystemState.SAFE_MODE.value:
            logger.critical("🛑 AUDIT FAILURE: System in SAFE_MODE. Manual intervention required.")
            return False
            
        # 3. Check for high lock density
        if vitals['database_locks'].get('status') == "CRITICAL":
             logger.error("🛑 AUDIT FAILURE: Critical DB Lock density. Performance collapse expected.")
             return False
             
        logger.info("🎉 [NEXUS:AUDIT] Audit Passed. System is resilient.")
        return True

nexus_audit = NexusAuditDashboard()
