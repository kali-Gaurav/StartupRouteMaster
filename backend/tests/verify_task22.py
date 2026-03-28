import asyncio
import os
import sys
import json

# Setup sys.path
sys.path.append(os.getcwd())

async def verify_dashboard():
    print("🛡️ Verifying Task 22: Circuit-Breaker Dashboard...")
    
    # Needs a partial boot for nodes and circuits
    from core.nexus.bootstrapper import nexus_boot
    from core.nexus.node import NexusNode
    from core.resilience import CircuitBreaker
    
    class MockNode(NexusNode):
        async def on_start(self): pass
        async def on_stop(self): pass
        
    node_a = MockNode("test_node_a")
    nexus_boot.register(node_a)
    
    # Create a circuit breaker
    cb = CircuitBreaker("test_circuit", failure_threshold=2)
    
    # Trigger a failure
    try:
        async def fail(): raise RuntimeError("BOOM")
        await cb.call(fail)
    except: pass
    
    from core.nexus.audit.dashboard import nexus_audit
    vitals = nexus_audit.get_system_vitals()
    
    print("\n--- Nexus Vitals ---")
    print(json.dumps(vitals, indent=2))
    
    # Verify presence of circuit status
    found_cb = False
    for c in vitals['circuit_breakers']:
        if c['name'] == 'test_circuit':
            found_cb = True
            print(f"\n✅ Found Circuit Breaker: {c['name']} (State: {c['state']}, Failures: {c['failures']})")
            
    if not found_cb:
        print("❌ Error: test_circuit not found in dashboard.")
        
    triage = nexus_audit.get_triage_report()
    print("\n--- Triage Report ---")
    print(triage)
    
if __name__ == "__main__":
    asyncio.run(verify_dashboard())
