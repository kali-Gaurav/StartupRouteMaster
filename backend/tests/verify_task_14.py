import sys
import os
from datetime import datetime
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.route_engine.turbo_router import TurboRouter

logging.basicConfig(level=logging.INFO)

def verify_task_14():
    print("\n>>> Verifying Task 14: City Cluster Expansion")
    router = TurboRouter()
    
    # Test Cluster Lookup directly
    pgt_cluster = router._get_city_cluster("PGT")
    print(f"  PGT Cluster: {pgt_cluster}")
    
    expected = ["PGT", "PGTN", "OTP"]
    is_ok = all(code in pgt_cluster for code in expected)
    
    if is_ok:
        print("\n✅ TASK 14 VERIFIED: City Clusters are working and expanding correctly.")
        return True
    else:
        print("\n❌ TASK 14 FAILED: Cluster expansion missing expected stations.")
        return False

if __name__ == "__main__":
    verify_task_14()
