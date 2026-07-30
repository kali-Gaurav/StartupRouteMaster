import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.agents.pricing_dynamic_agent import pricing_dynamic_agent

async def test_dynamic_pricing_logic():
    print("\n--- Testing Dynamic Pricing logic ---")
    
    # 1. Normal Case: 50% Occupancy
    context_normal = {
        "source": "NDLS",
        "destination": "HWH",
        "current_occupancy": 50,
        "physical_capacity": 100
    }
    
    res_normal = await pricing_dynamic_agent.run(context_normal)
    print(f"Normal Fee: {res_normal['final_fee']} INR")
    
    # 2. Critical Capacity Case: 95% Occupancy
    # Virtual capacity will be applied (usually +10-15 seats)
    # If occupancy is 95, it's still high utilization
    context_high = {
        "source": "NDLS",
        "destination": "HWH",
        "current_occupancy": 95,
        "physical_capacity": 100
    }
    
    res_high = await pricing_dynamic_agent.run(context_high)
    print(f"High Demand Fee: {res_high['final_fee']} INR | Reason: {res_high['reason']}")
    
    assert res_high["final_fee"] > res_normal["final_fee"], "High occupancy should trigger surge"
    assert "Critical capacity" in res_high["reason"] or "High demand" in res_high["reason"]
    
    print("Test Dynamic Pricing Passed!")

if __name__ == "__main__":
    asyncio.run(test_dynamic_pricing_logic())
