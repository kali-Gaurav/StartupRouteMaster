"""
🧪 E2E ALGORITHM VALIDATION — RouteMaster Phase 1-3 Unified Test
Validates the entire pipeline: 
Search -> 2-Transfer -> Pareto Optimization -> Redistribution -> Seat Allocation
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.append(str(_root))

from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Persona
from core.allocation.seat_allocator import seat_allocator, Passenger, PassengerCategory, BerthPreference

# Setup logging to see the internal "Patent Logic" triggers
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("E2E_VALIDATION")

async def run_validation():
    logger.info("🚀 Starting Full E2E Algorithm Validation...")
    
    from core.route_engine import get_route_engine
    engine = get_route_engine()
    orchestrator = UnifiedRoutingOrchestrator(engine)
    
    # 1. TEST SEARCH: NDLS -> HWH (High Demand Corridor)
    constraints = RouteConstraints(persona=Persona.COMFORT)
    request = RoutingRequest(
        source_code="NDLS",
        destination_code="HWH",
        departure_date=datetime.now() + timedelta(days=7),
        persona=Persona.COMFORT,
        limit=10,
        constraints=constraints
    )

    
    logger.info("🔍 PHASE 1/2: Running Orchestrated Search (Direct, 1-T, 2-T)...")
    from database.session import initialize_database_pools, SessionLocal
    await initialize_database_pools()
    db = SessionLocal()
    
    # [PATENT VALIDATION] Saturate a train to trigger redistribution
    from services.demand_forecaster import demand_forecaster
    travel_date = (datetime.now() + timedelta(days=7)).date()
    logger.info(f"📈 [STRESS] Saturating top trains for {travel_date}...")
    
    # 12312 (Kalka Mail) leaves from DLI
    demand_forecaster.record_booking_event("12312", "DLI", "HWH", travel_date, 600)
    # 12304 (Poorva Express) leaves from NDLS
    demand_forecaster.record_booking_event("12304", "NDLS", "HWH", travel_date, 600)
    # 12301 (Rajdhani) leaves from NDLS
    demand_forecaster.record_booking_event("12301", "NDLS", "HWH", travel_date, 600)
    
    try:
        routes = await orchestrator.stream_all_tiers(request)
        
        logger.info(f"✅ Found {len(routes)} total routes.")
        for i, r in enumerate(routes[:3]):
            trains = [s.train_number for s in r.segments]
            logger.info(f"  Route {i}: Trains {trains}")
        
        # Validate Pareto Labels
        pareto_tags = []
        for r in routes:
            tags = r.metadata.get("persona_tags", [])
            if tags:
                pareto_tags.extend(tags)
        logger.info(f"⚖️ Pareto Tags Found: {pareto_tags}")
        
        # Validate Redistribution
        redist_summary = request.metadata.get("redistribution_summary")
        if redist_summary:
            logger.info(f"🔄 REDISTRIBUTION TRIGGERED: {redist_summary}")
        else:
            logger.warning("⚠️ No redistribution options generated (maybe trains aren't 'saturated' in mock data)")

        # 2. TEST ALLOCATION: Group of 4 with Senior Citizen & Child
        logger.info("💺 PHASE 3: Testing Intelligent Seat Allocation with Dynamic Overbooking...")
        passengers = [
            Passenger("P1", "Gaurav", 30, "M", PassengerCategory.ADULT_MALE, BerthPreference.LOWER),
            Passenger("P2", "Anjali", 28, "F", PassengerCategory.ADULT_FEMALE, BerthPreference.SIDE_LOWER),
            Passenger("P3", "Elder", 65, "M", PassengerCategory.SENIOR_MALE, BerthPreference.LOWER),
            Passenger("P4", "Kid", 8, "M", PassengerCategory.CHILD, BerthPreference.NO_PREFERENCE)
        ]
        
        allocation = await seat_allocator.allocate_booking(
            booking_id="TEST_B1",
            train_number="12301",
            from_station="NDLS",
            to_station="HWH",
            travel_date=(datetime.now() + timedelta(days=7)).date(),
            class_code="3A",
            passengers=passengers,
            db=db
        )
        
        logger.info(f"✅ Allocation Complete: Status {[a.status.value for a in allocation.allocations]}")
        logger.info(f"📊 Comfort Score: {allocation.overall_comfort_score} | Group Integrity: {allocation.group_integrity_score}")
        
        # Check if dynamic overbooking notes are present
        overbook_notes = [a.notes for a in allocation.allocations if "Dynamic Overbooking" in a.notes]
        if overbook_notes:
            logger.info(f"📈 Overbooking confirmed in results: {overbook_notes[0]}")

    except Exception as e:
        logger.error(f"❌ Validation Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_validation())
