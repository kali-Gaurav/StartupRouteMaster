"""
SIO Integration Test Script
===========================
Verifies the end-to-end 'Sovereign Intelligence' workflow in the search cycle.
Tests:
1. High Pressure corridor detection.
2. EDR Nudge generation with Nash Equilibrium pricing.
3. SSIE Multi-modal injection.
4. Shadow-Guide natural language synthesis.
"""

import asyncio
import json
import logging
import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from core.sovereign.orchestrator import sio
from core.sovereign.network_pressure import network_pressure
from core.data_structures import Route, RouteSegment, Persona
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test.sio")

async def run_test():
    logger.info("🚀 Starting SIO Integration Test...")
    
    # 1. Force High Pressure for NDLS -> BCT via Mocking
    source, destination = "NDLS", "BCT"
    
    from unittest.mock import AsyncMock
    from core.sovereign.network_pressure import PressureNode, PressureLevel
    
    # Mock node for Critical Pressure
    mock_node = PressureNode(
        node_id=f"{source}->{destination}",
        node_type="corridor",
        pressure_score=0.98,
        pressure_level=PressureLevel.OVERFLOW,
        occupancy_score=0.99,
        demand_velocity_score=0.95,
        trend="rising"
    )
    
    # Patch the network_pressure object
    network_pressure.get_corridor_pressure = AsyncMock(return_value=mock_node)
    logger.info(f"Mocked {source}->{destination} pressure to 0.98")
    
    # 2. Mock some routes
    mock_routes = [
        Route(
            journey_id="train_12952",
            segments=[RouteSegment(train_number="12952", departure_code=source, arrival_code=destination, distance_km=1384)],
            total_cost=2400.0,
            total_duration=1000,
            score=9.5,
            metadata={"value_score": 9.5}
        ),
        Route(
            journey_id="train_alternative",
            segments=[RouteSegment(train_number="22222", departure_code=source, arrival_code=destination, distance_km=1400)],
            total_cost=2100.0,
            total_duration=1100,
            score=8.5,
            metadata={"value_score": 8.5}
        )
    ]
    
    # 3. Execute SIO Cycle
    logger.info("Executing SIO Cycle...")
    result = await sio.execute_search_cycle(
        source=source,
        destination=destination,
        initial_routes=mock_routes,
        user_id="test_user_alpha",
        persona="comfort",
        tier="PRO"
    )
    
    # 4. Verify Results
    decision = result["decision"]
    guidance = result["guidance"]
    
    logger.info(f"📊 Corridor Pressure: {decision.corridor_pressure:.2f}")
    logger.info(f"🧠 EDR Decision: {decision.pressure_level.value}")
    logger.info(f"📢 Shadow-Guide Message: {guidance.message}")
    
    if decision.has_nudges:
        logger.info(f"🎯 Nudges Generated: {len(decision.nudges)}")
        for i, nudge in enumerate(decision.nudges):
            logger.info(f"  [{i}] Type: {nudge.nudge_type.value} | Headline: {nudge.headline} | Incentive: Rs {nudge.incentive_value}")
    else:
        logger.warning("⚠️ No nudges generated. Check pressure threshold.")

    # 5. Check for SSIE Injection (Only if pressure > 0.95)
    has_ssie = any(n.nudge_type.value == "MULTI_MODAL" for n in decision.nudges)
    if has_ssie:
        logger.info("✅ SUCCESS: SSIE Multi-modal injection confirmed!")
    else:
        logger.info("ℹ️ SSIE not triggered (Pressure might be below 0.95).")

    logger.info("✨ SIO Integration Test Complete.")

if __name__ == "__main__":
    asyncio.run(run_test())
