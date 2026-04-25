import asyncio
import logging
import time
from sqlalchemy import text
from database.session import initialize_database_pools, SessionTransit
from core.nexus.telemetry import nexus_telemetry
from services.cache_service import cache_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nexus_audit")

class NexusMasterAudit:
    """
    [Elite Audit] The final verification for the Nexus Infrastructure.
    Verifies state across DB, Cache, and Internal Services.
    """
    def __init__(self):
        self.db = None
        self.stats = {}

    async def init(self):
        await initialize_database_pools()
        self.db = SessionTransit()

    async def audit_telemetry_health(self):
        print("\n--- NEXUS TELEMETRY AUDIT ---")
        report = nexus_telemetry.get_system_report()
        self.stats['telemetry'] = report
        
        status = report.get("system_status", "UNKNOWN")
        if status == "HEALTHY":
            print("[OK] System Status is HEALTHY.")
        else:
            print(f"[CRITICAL] System Status is {status}!")
            
        print(f"Uptime: {report.get('uptime_seconds', 0)}s")
        print(f"Active Missions (Guardian): {report.get('guardian', {}).get('active_missions', 0)}")

    async def audit_database_consistency(self):
        print("\n--- DATABASE CONSISTENCY AUDIT ---")
        try:
            # Check for orphaned bookings (Task 117.9)
            orphans = self.db.execute(text("""
                SELECT COUNT(*) FROM bookings 
                WHERE user_id NOT IN (SELECT id FROM users)
            """)).scalar()
            
            if orphans > 0:
                print(f"[WARN] Found {orphans} orphaned bookings (missing user reference).")
            else:
                print("[OK] No orphaned bookings found.")

            # Check for missing station metadata in search logs
            missing_meta = self.db.execute(text("""
                SELECT COUNT(*) FROM route_search_logs 
                WHERE src NOT IN (SELECT code FROM station_realtime_heartbeats)
            """)).scalar()
            
            if missing_meta > 100: # Tolerance for external/fake logs
                print(f"[WARN] {missing_meta} search logs reference unknown station codes.")
            else:
                print("[OK] Station metadata alignment is acceptable.")

        except Exception as e:
            print(f"[FAIL] DB Audit failed: {e}")

    async def audit_cache_perf(self):
        print("\n--- CACHE INTEGRITY AUDIT ---")
        if not cache_service.is_available():
            print("[FAIL] Redis is unavailable.")
            return

        start = time.perf_counter()
        cache_service.set("audit_probe", "nexus_val", expire=10)
        val = cache_service.get("audit_probe")
        latency = (time.perf_counter() - start) * 1000
        
        if val == "nexus_val":
            print(f"[OK] Redis Probe Success. Latency: {latency:.2f}ms")
        else:
            print("[FAIL] Redis data corruption or retrieval failure.")

    async def run(self):
        await self.init()
        await self.audit_telemetry_health()
        await self.audit_database_consistency()
        await self.audit_cache_perf()
        print("\n--- MASTER AUDIT COMPLETE ---")

if __name__ == "__main__":
    audit = NexusMasterAudit()
    asyncio.run(audit.run())
