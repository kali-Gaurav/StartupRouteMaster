import sys
import os
from services.tax_engine_service import tax_engine

def verify_task_5():
    print("=== Verifying Task 5: Platform Fee & GST Engine ===")
    
    # 1. Test standard calculation
    # Base: 1000. Fee (2%): 20. GST (18% of 20): 3.6. Total: 1023.6 -> 1024
    print("Testing standard calculation (Base: 1000)...")
    breakdown = tax_engine.calculate_breakdown(1000.0)
    print(f"Breakdown: {breakdown}")
    assert breakdown["base_fare"] == 1000.0
    assert breakdown["platform_fee"] == 20.0
    assert breakdown["gst"] == 3.6
    assert breakdown["total"] == 1024.0
    print("[OK] Standard Calculation")

    # 2. Test Minimum Fee
    # Base: 100. 2% is 2.0, but min is 20.0. GST: 3.6. Total: 123.6 -> 124
    print("Testing minimum fee (Base: 100)...")
    breakdown = tax_engine.calculate_breakdown(100.0)
    print(f"Breakdown: {breakdown}")
    assert breakdown["platform_fee"] == 20.0
    assert breakdown["total"] == 124.0
    print("[OK] Minimum Fee")

    # 3. Test Maximum Fee
    # Base: 10000. 2% is 200, but max is 150.0. GST: 27.0. Total: 10177
    print("Testing maximum fee (Base: 10000)...")
    breakdown = tax_engine.calculate_breakdown(10000.0)
    print(f"Breakdown: {breakdown}")
    assert breakdown["platform_fee"] == 150.0
    assert breakdown["total"] == 10177.0
    print("[OK] Maximum Fee")

    # 4. Test Discount Code
    print("Testing discount code 'FIRSTFREE'...")
    breakdown = tax_engine.calculate_breakdown(1000.0, "FIRSTFREE")
    print(f"Breakdown: {breakdown}")
    assert breakdown["platform_fee"] == 0.0
    assert breakdown["gst"] == 0.0
    assert breakdown["total"] == 1000.0
    print("[OK] Discount Logic")

    print("=== Task 5 Verification Complete ===")

if __name__ == "__main__":
    verify_task_5()
