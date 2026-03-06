import sys
import os
from services.merchant_vpa_service import merchant_vpa_service
from services.cache_service import cache_service

def verify_task_4():
    print("=== Verifying Task 4: Multi-VPA Merchant Load Balancer ===")
    
    # 1. Test Weighted Rotation
    print("Testing VPA rotation...")
    vpas_seen = {}
    for _ in range(100):
        vpa_info = merchant_vpa_service.get_next_vpa()
        vpa = vpa_info["vpa"]
        vpas_seen[vpa] = vpas_seen.get(vpa, 0) + 1
    
    print(f"VPA distribution over 100 trials: {vpas_seen}")
    assert len(vpas_seen) >= 2 # Should see multiple VPAs
    # Node A (weight 5) should generally have more than Node B (weight 3)
    if "gauravnagar@okaxis" in vpas_seen and "routemaster@axl" in vpas_seen:
        assert vpas_seen["gauravnagar@okaxis"] > vpas_seen.get("emergency_vpa@okhdfc", 0)
    print("[OK] Weighted Rotation")

    # 2. Test Health Filtering
    print("Testing health-based exclusion...")
    vpa_to_block = "gauravnagar@okaxis"
    merchant_vpa_service.mark_health(vpa_to_block, "blocked")
    
    blocked_seen = False
    for _ in range(20):
        vpa_info = merchant_vpa_service.get_next_vpa()
        if vpa_info["vpa"] == vpa_to_block:
            blocked_seen = True
            break
    
    assert blocked_seen is False
    print(f"[OK] Health Filtering (Blocked {vpa_to_block})")
    
    # Restore health
    merchant_vpa_service.mark_health(vpa_to_block, "healthy")

    # 3. Test Daily Volume Limits
    print("Testing volume-based exclusion...")
    vpa_limit = "routemaster@axl"
    # Set volume just below limit
    merchant_vpa_service.record_volume(vpa_limit, 99999) 
    # This next record should push it over (limit is 100,000)
    merchant_vpa_service.record_volume(vpa_limit, 2)
    
    limit_exceeded_seen = False
    for _ in range(20):
        vpa_info = merchant_vpa_service.get_next_vpa()
        if vpa_info["vpa"] == vpa_limit:
            limit_exceeded_seen = True
            break
            
    assert limit_exceeded_seen is False
    print(f"[OK] Volume Limit Filtering (Exceeded {vpa_limit})")

    print("=== Task 4 Verification Complete ===")

if __name__ == "__main__":
    verify_task_4()
