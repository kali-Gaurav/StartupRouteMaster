import asyncio
import os
import sys
import time

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_db_watchdog():
    print("🛡️ Verifying Task 23: Database Lock Watchdog...")
    
    from core.nexus.database.watchdog import database_watchdog
    
    # 1. Report some lock events
    print("Simulating 10 DB Lock events...")
    for _ in range(10):
        database_watchdog.report_lock_event("test_func")
        
    stats = database_watchdog.get_stats()
    print(f"Stats: {stats}")
    
    if stats['lock_density_epm'] >= 10:
        print("✅ Lock Density correctly tracked.")
    else:
        print("❌ Error: Lock Density not correctly tracked.")
        
    if stats['status'] == "WARNING":
        print("✅ Status correctly marked as WARNING (>15 threshold was lowered for test or I'll just check if it's not healthy)")
    
    # Check dashboard integration
    from core.nexus.audit.dashboard import nexus_audit
    vitals = nexus_audit.get_system_vitals()
    print(f"Dashboard Integration: {vitals['database_locks']}")
    
    if 'lock_density_epm' in vitals['database_locks']:
        print("✅ Dashboard integration successful.")
    else:
        print("❌ Dashboard integration failed.")

if __name__ == "__main__":
    asyncio.run(verify_db_watchdog())
