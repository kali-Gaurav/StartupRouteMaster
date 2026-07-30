import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.agents.cancellation_prediction_agent import cancellation_prediction_agent
from services.agents.overbooking_agent import overbooking_agent

async def test_overbooking_flow():
    print("\n--- Testing Overbooking Flow ---")
    
    # 1. Test Cancellation Prediction
    # High risk case: Weekend travel, expensive booking, non-verified user
    context_high_risk = {
        "booking_date": "2024-12-24", # Tuesday
        "travel_date": "2024-12-28",  # Saturday
        "is_weekend": True,
        "is_verified_user": False,
        "historical_cancellation_rate": 0.2
    }
    
    cancel_res = await cancellation_prediction_agent.run(context_high_risk)
    prob = cancel_res["cancellation_probability"]
    print(f"High Risk Probability: {prob:.2f}")
    
    # 2. Test Overbooking Calculation
    # Physical capacity: 100
    # Demand: 120 (Attempting to book 20 extra)
    # Target: Should allow some virtual seats
    overbook_context = {
        "physical_capacity": 100,
        "demand_forecast": 120,
        "cancellation_risk": prob
    }
    
    overbook_res = await overbooking_agent.run(overbook_context)
    virtual_cap = overbook_res["virtual_capacity"]
    overbook_count = overbook_res["overbook_count"]
    
    print(f"Physical: 100 | Virtual: {virtual_cap} | Limit: {overbook_count}")
    
    assert virtual_cap > 100, "Virtual capacity should be higher than physical"
    assert virtual_cap <= 115, "Virtual capacity should not exceed 115% cap"
    print("✅ Overbooking Logic Passed!")

if __name__ == "__main__":
    asyncio.run(test_overbooking_flow())
