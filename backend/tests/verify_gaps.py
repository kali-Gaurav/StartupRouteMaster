import asyncio
import os
import sys
import json

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_gaps():
    print("🛡️ Verifying Phase 3.5: Resilience Gap Closures...")
    
    # 1. Verify Integrity Engine
    from utils.integrity import integrity_engine
    integrity_engine.record("test_unit", "GAP_CHECK", severity="SUCCESS", details={"status": "OK"})
    
    if os.path.exists("nexus_integrity.log"):
        print("✅ Atomic Integrity Log created.")
        with open("nexus_integrity.log", "r") as f:
             last_line = f.readlines()[-1]
             print(f"   Last entry: {last_line.strip()}")
    else:
        print("❌ Error: nexus_integrity.log missing.")
        
    # 2. Verify Dashboard with new fields
    from core.nexus.audit.dashboard import nexus_audit
    triage = nexus_audit.get_triage_report()
    print("\n--- Triage Report (New) ---")
    print(triage)
    
    print("\n🎉 Gap Closure Audit Complete.")

if __name__ == "__main__":
    asyncio.run(verify_gaps())
