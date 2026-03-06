import sys
import os
from services.merchant_vpa_service import merchant_vpa_service
from services.cache_service import cache_service

def verify_task_4_gaps():
    print("=== Verifying Task 4 Gaps: Resting State & Regional Routing ===")
    
    # Clean up state from previous tests
    for vpa in ["gauravnagar@okaxis", "routemaster@axl", "emergency_vpa@okhdfc"]:
        cache_service.delete(f"{merchant_vpa_service.DAILY_VOLUME_PREFIX}{vpa}:{os.environ.get('TEST_DATE', '')}")
        # To be safe, clear today's specifically
        from datetime import date
        today = date.today().isoformat()
        cache_service.delete(f"{merchant_vpa_service.DAILY_VOLUME_PREFIX}{vpa}:{today}")
        cache_service.delete(f"{merchant_vpa_service.VPA_RESTING_PREFIX}{vpa}")
        
    # 1. Test Regional Routing
    print("Testing Regional Routing (NORTH)...")
    vpa_north = merchant_vpa_service.get_next_vpa(user_region="NORTH")
    assert vpa_north["vpa"] == "gauravnagar@okaxis"
    assert vpa_north["region"] == "NORTH"
    print("[OK] Routed to North node")
    
    print("Testing Regional Routing (SOUTH)...")
    vpa_south = merchant_vpa_service.get_next_vpa(user_region="SOUTH")
    assert vpa_south["vpa"] == "routemaster@axl"
    assert vpa_south["region"] == "SOUTH"
    print("[OK] Routed to South node")
    
    print("Testing Regional Fallback (EAST - no specific node)...")
    vpa_east = merchant_vpa_service.get_next_vpa(user_region="EAST")
    # Should fallback to any available node, including ALL
    assert vpa_east is not None
    print("[OK] Fallback routing works for unknown region")

    # 2. Test Resting State
    print("Testing Burst Volume Resting State...")
    vpa_to_test = "gauravnagar@okaxis"
    
    # Clear existing state
    cache_service.delete(f"{merchant_vpa_service.DAILY_VOLUME_PREFIX}{vpa_to_test}")
    cache_service.delete(f"{merchant_vpa_service.VPA_RESTING_PREFIX}{vpa_to_test}")
    
    # Simulate a sudden burst of 60k (Limit is 100k, 50k is threshold)
    merchant_vpa_service.record_volume(vpa_to_test, 60000.0)
    
    assert merchant_vpa_service.is_resting(vpa_to_test) is True
    print("[OK] VPA entered RESTING state after >50% burst")

    # Ensure it's not selected when resting
    selected = merchant_vpa_service.get_next_vpa(user_region="NORTH")
    # Even if we ask for NORTH, the North node is resting, so it should fallback
    if selected:
        assert selected["vpa"] != vpa_to_test
    print("[OK] Resting VPA is excluded from selection")

    # 3. Test Dashboard Stats
    print("Testing Admin Dashboard Stats...")
    stats = merchant_vpa_service.get_dashboard_stats()
    assert len(stats) == 3
    assert stats[0]["status"] == "RESTING" # North node is resting
    print("[OK] Dashboard stats generated correctly")

    print("=== Task 4 Gaps Verification Complete ===")

if __name__ == "__main__":
    verify_task_4_gaps()
