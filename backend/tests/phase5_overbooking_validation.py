import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.agents.overbooking_agent import overbooking_agent
from services.agents.pricing_dynamic_agent import pricing_dynamic_agent
from services.agents.cancellation_prediction_agent import cancellation_prediction_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("phase5.validation")

async def run_phase5_validation():
    logger.info("\n🚀 STARTING PHASE 5: PREDICTIVE OVERBOOKING & REVENUE VALIDATION\n")
    
    # SCENARIO 1: Standard Route, Low Demand
    logger.info("--- [SCENARIO 1: Standard Route, Low Demand] ---")
    route_low = {"source": "NDLS", "destination": "CNB", "days_to_departure": 30, "class_type": "3A", "distance": 440}
    
    overbook_low = await overbooking_agent.calculate_overbook_limit("T12301", 100, route_low)
    pricing_low = await pricing_dynamic_agent.calculate_convenience_fee("NDLS", "CNB", current_occupancy=20, physical_capacity=100)
    
    logger.info(f"Prob: {overbook_low['cancellation_probability']:.2f} | Overbook: +{overbook_low['overbook_count']} | Fee: ₹{pricing_low['final_fee']}")
    assert pricing_low["final_fee"] == 20.0, "Low demand with overbooking inventory should have discount fee (20.0)"

    # SCENARIO 2: High Demand, High Cancellation Route (Waitlist simulation)
    logger.info("\n--- [SCENARIO 2: High Demand, Saturated Physical Capacity] ---")
    route_high = {"source": "NDLS", "destination": "HWH", "days_to_departure": 45, "class_type": "SL", "distance": 1450}
    
    overbook_high = await overbooking_agent.calculate_overbook_limit("T12302", 500, route_high)
    # Even if physically full (500/500), overbooking should allow more
    pricing_high = await pricing_dynamic_agent.calculate_convenience_fee("NDLS", "HWH", current_occupancy=500, physical_capacity=500)
    
    logger.info(f"Prob: {overbook_high['cancellation_probability']:.2f} | Overbook: +{overbook_high['overbook_count']} | Fee: ₹{pricing_high['final_fee']} ({pricing_high['reason']})")
    assert pricing_high["final_fee"] > 25.0, "High demand should trigger surge"
    assert overbook_high["overbook_count"] > 0, "High cancellation route should allow overbooking"

    # SCENARIO 3: Yield Max (Approaching Virtual Capacity)
    logger.info("\n--- [SCENARIO 3: Yield Max (Full Virtual Capacity)] ---")
    current_occ = overbook_high["virtual_capacity"] - 2
    pricing_max = await pricing_dynamic_agent.calculate_convenience_fee("NDLS", "HWH", current_occupancy=current_occ, physical_capacity=500)
    
    logger.info(f"Occ: {current_occ}/{overbook_high['virtual_capacity']} | Fee: ₹{pricing_max['final_fee']} ({pricing_max['reason']})")
    assert pricing_max["final_fee"] >= 62.5, "Yield Max should trigger 2.5x surge"

    # SCENARIO 4: Load Balance Discount
    logger.info("\n--- [SCENARIO 4: Load Balance Discount (Empty Virtual Inventory)] ---")
    pricing_disc = await pricing_dynamic_agent.calculate_convenience_fee("NDLS", "HWH", current_occupancy=50, physical_capacity=500)
    
    logger.info(f"Occ: 50/{overbook_high['virtual_capacity']} | Fee: ₹{pricing_disc['final_fee']} ({pricing_disc['reason']})")
    assert pricing_disc["final_fee"] == 20.0, "Under-utilized virtual capacity should trigger 0.8x discount"

    logger.info("\n✅ PHASE 5 VALIDATION COMPLETE: All Autonomous Agents Working in Sync.\n")

if __name__ == "__main__":
    asyncio.run(run_phase5_validation())
