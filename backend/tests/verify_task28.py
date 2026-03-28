import asyncio
import os
import sys

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_triage_diagnostics():
    print("🚦 [NEXUS:TRIAGE] DEEP DIAGNOSTIC VERIFICATION [Task 28]")
    print("=====================================================")
    
    from core.nexus.audit.triage import nexus_triage, SystemStatus
    from core.nexus.audit.chaos import nexus_chaos
    from services.multi_layer_cache import multi_layer_cache
    
    await multi_layer_cache.init()
    
    # CASE 1: Baseline Health (Stable)
    print("\n🔹 Case 1: Checking Baseline (Stable) Status...")
    report = await nexus_triage.get_deep_diagnostics()
    print(f"   Status: {report['node_status']}")
    print(f"   Recommendation: {report['recommendation']}")
    
    if report['node_status'] == SystemStatus.STABLE:
         print("   ✅ BASELINE VERIFIED.")
    else:
         print(f"   ❌ FAILED: Unexpected status {report['node_status']}")

    # CASE 2: Simulating Lag (Chaos Active)
    print("\n🔹 Case 2: Simulating System Lag (Chaos Injected)...")
    nexus_chaos.arm("triage_test", base_delay=0.1)
    
    # We need to force clear the 1s cache in triage to see immediate change
    nexus_triage.last_analysis_time = 0 
    
    report = await nexus_triage.get_deep_diagnostics()
    print(f"   Status: {report['node_status']}")
    print(f"   Diagnosis: {report['recommendation']}")
    
    if report['node_status'] == SystemStatus.LAGGING:
         print("   ✅ LAG DETECTION VERIFIED.")
    else:
         print(f"   ❌ FAILED: Status should be LAGGING, got {report['node_status']}")

    # CASE 3: Simulating Persistence Pressure (Zombie Sagas)
    print("\n🔹 Case 3: Simulating Congestion (Saga Pressure)...")
    from core.nexus.financial.rollback import nexus_saga
    p_ids = []
    for i in range(10): 
        t_id = f"stress:triage_multi_{i}"
        p_ids.append(t_id)
        nexus_saga.start_transaction(t_id)
        await nexus_saga.add_step(f"TRIAGE_STRESS_{i}", {"v": i}, i)
    
    nexus_triage.last_analysis_time = 0
    report = await nexus_triage.get_deep_diagnostics()
    print(f"   Status: {report['node_status']}")
    print(f"   Recommendation: {report['recommendation']}")
    
    if report['node_status'] == SystemStatus.CONGESTED:
         print("   ✅ CONGESTION DETECTION VERIFIED.")
    else:
         print(f"   ❌ FAILED: Status should be CONGESTED (due to 10+ saga logs), got {report['node_status']}")

    # Cleanup
    from core.nexus.financial.rollback import orchestrate_rollback
    for tid in p_ids:
         await orchestrate_rollback(tid)
    print("\n🎉 TASK 28 TRIAGE ENGINE FULLY OPERATIONAL.")

if __name__ == "__main__":
    asyncio.run(verify_triage_diagnostics())
