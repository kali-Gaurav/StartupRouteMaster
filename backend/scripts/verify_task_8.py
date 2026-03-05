import sys
import os
import struct

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.emergency.risk_service import risk_service

def verify():
    print("--- 🚨 Task 8: Memory-Mapped Top-100 Danger Zone Verification ---")
    
    # Matching backend/app.py logic where root is backend/
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    index_path = os.path.join(base_dir, "top_danger.bin")
    
    print(f"DEBUG: Looking for index at {index_path}")
    if not os.path.exists(index_path):
        print("❌ Failure: top_danger.bin not found.")
        return

    # 1. Read one known zone from binary
    with open(index_path, "rb") as f:
        chunk = f.read(9)
        lat, lng, score = struct.unpack('ffB', chunk)
        print(f"Testing against known Top-Danger Zone at ({lat}, {lng})")

    # 2. Query risk_service
    res = risk_service.check_area_risk(lat, lng)
    print(f"Risk Result: {res['risk_level']} (Score: {res['score']})")
    
    found_top = any(z.get('description') == 'TOP_CRITICAL_ZONE' for z in res.get('nearby_risk_zones', []))
    
    if found_top:
        print("\n🏆 TASK 8 VERIFIED: Fastest-path O(1) linear scan for Top-100 active.")
    else:
        print("\n❌ TASK 8 FAILED: Fast-path zone not detected correctly.")

if __name__ == "__main__":
    verify()
