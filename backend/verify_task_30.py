import sys
import os
import uuid
import asyncio

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.tatkal_scheduler_service import tatkal_scheduler

async def verify_task_30():
    print("=== Verifying Task 30: Tatkal Timing Precision ===")
    
    booking_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    # 1. Test Probability Calculator (Task 30.10)
    print("Testing Probability Calculator...")
    
    # High demand, high ping = low probability
    prob_high_demand = tatkal_scheduler.calculate_success_probability(route_popularity=9, ping_ms=300, previous_attempts=0)
    assert prob_high_demand < 60.0
    
    # Low demand, low ping = high probability
    prob_low_demand = tatkal_scheduler.calculate_success_probability(route_popularity=2, ping_ms=50, previous_attempts=2)
    assert prob_low_demand > prob_high_demand
    
    print(f"[OK] Probability calculated accurately (Low: {prob_high_demand}%, High: {prob_low_demand}%)")

    # 2. Test Force Start (Task 30.9 & Orchestration logic)
    print("Testing Force Start Execution...")
    
    # Sync NTP
    await tatkal_scheduler.sync_ntp_time()
    assert tatkal_scheduler.ntp_offset_ms == 15
    
    # Execute Sequence
    result = await tatkal_scheduler.execute_tatkal_sequence(
        booking_id=booking_id,
        user_id=user_id,
        is_ac=True,
        is_force_start=True
    )
    
    assert result["success"] is True
    assert "payload fired successfully" in result["message"]
    print("[OK] Force start triggered sequence successfully (including retries and NTP sync)")

    print("=== Task 30 Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_30())
