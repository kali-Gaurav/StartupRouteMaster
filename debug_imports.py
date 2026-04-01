import sys
import os
sys.path.append(os.path.join(os.getcwd(), "backend"))
try:
    from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
    print("SUCCESS: Orchestrator imported")
except ImportError as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
