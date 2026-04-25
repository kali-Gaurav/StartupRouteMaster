import asyncio
import logging
import sys
import os
from typing import List
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.data_structures import Route, RouteSegment, Persona
from services.agents.arbitrage_agent import arbitrage_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation.phase6")

def create_mock_route(journey_id: str, mode: str, cost: float, duration_mins: int) -> Route:
    route = Route(
        journey_id=journey_id,
        segments=[],
        total_cost=cost,
        total_duration=duration_mins,
        transfers=0,
        score=0.0
    )
    route.metadata["mode"] = mode
    route.metadata["reliability"] = 0.95 if mode == "FLIGHT" else 0.85
    return route

async def validate_arbitrage():
    logger.info("🚀 Starting Phase 6: Arbitrage Validation")

    # Scenario: Premium User traveling long distance
    # Option 1: Rail (Slow, Cheap)
    # Option 2: Air (Fast, Expensive but good value for Premium)
    
    routes = [
        create_mock_route("rail_001", "RAIL", 1500.0, 1440), # 24 hours, 1500 INR
        create_mock_route("air_001", "FLIGHT", 4500.0, 120), # 2 hours, 4500 INR
    ]

    context = {
        "routes": routes,
        "persona": Persona.PREMIUM
    }

    logger.info(f"Analyzing {len(routes)} routes for PREMIUM persona...")
    result = await arbitrage_agent.run(context)
    
    logger.info(f"Arbitrage Found: {result['arbitrage_found']}")
    
    for r in routes:
        tag = r.metadata.get("arbitrage_tag", "NONE")
        score = r.metadata.get("arbitrage_score", 0.0)
        gen_cost = r.metadata.get("generalized_cost", 0.0)
        logger.info(f"Route {r.journey_id} ({r.metadata['mode']}): Tag={tag}, Score={score}, GenCost={gen_cost:.2f}")

    # Assertions
    assert result["arbitrage_found"] >= 1, "Should find at least one arbitrage opportunity"
    assert routes[1].metadata.get("arbitrage_tag") in ["BEST_VALUE", "TIME_ARBITRAGE"], "Flight should be tagged as arbitrage for Premium"
    
    logger.info("✅ Phase 6 Validation Successful!")

if __name__ == "__main__":
    asyncio.run(validate_arbitrage())
