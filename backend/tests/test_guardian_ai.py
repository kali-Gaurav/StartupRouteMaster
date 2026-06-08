import asyncio
import sys
import logging
from datetime import datetime

# Configure basic logging to see output
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("test_guardian")

async def run_tests():
    try:
        from guardian_ai.mission_manager import mission_manager
        from guardian_ai.safety_engine import safety_engine
        from guardian_ai.models import RiskLevel
        from guardian_ai.memory_store import guardian_memory
        from services.cache_service import cache_service

        logger.info("Initializing Cache connections...")
        # Since cache_service might need an initialized pool, we fallback to a safe mock if it's not connected 
        # But let's assume it works or fails fast.
        
        test_user_id = "test_user_123"
        test_journey = {
            "pnr": "1234567890",
            "source": "NDLS",
            "destination": "MMCT",
            "departure_time": datetime.utcnow().isoformat(),
            "arrival_time": datetime.utcnow().isoformat()
        }

        logger.info("=== 1. Testing Mission Creation ===")
        mission = await mission_manager.start_mission(test_user_id, test_journey)
        if not mission:
            raise ValueError("Failed to create mission")
        logger.info(f"✅ Mission created: {mission.mission_id}")

        logger.info("=== 2. Testing Memory Persistence ===")
        retrieved_mission = await guardian_memory.get_mission(mission.mission_id)
        if not retrieved_mission:
            raise ValueError("Failed to retrieve mission from memory store")
        logger.info(f"✅ Mission retrieved from memory")

        logger.info("=== 3. Testing Location Update ===")
        updated_mission = await mission_manager.update_location(mission.mission_id, 28.6139, 77.2090, "NDLS")
        if not updated_mission.location.last_known_station == "NDLS":
            raise ValueError("Failed to update location")
        logger.info(f"✅ Location updated successfully")

        logger.info("=== 4. Testing Safety Engine (Behavior Analysis) ===")
        test_message = "I am scared, someone is following me!"
        logger.info(f"Sending message: '{test_message}'")
        analyzed_mission = await safety_engine.process_user_message(test_user_id, test_message)
        
        if analyzed_mission.risk_score == 0:
            raise ValueError("Safety engine failed to detect risk")
        
        logger.info(f"✅ Safety Engine processed message.")
        logger.info(f"   New Risk Score: {analyzed_mission.risk_score}")
        logger.info(f"   New Risk Level: {analyzed_mission.risk_level.value}")
        logger.info(f"   Logged Events: {len(analyzed_mission.events)}")
        
        logger.info("=== 5. Testing Action Evaluator ===")
        directives = await safety_engine.evaluate_mission_state(analyzed_mission)
        logger.info(f"✅ Directives generated: {directives}")
        
        # Test autonomous loop tick
        from guardian_ai.monitoring_loop import guardian_loop
        logger.info("=== 6. Testing Autonomous Monitoring Loop Tick ===")
        await guardian_loop._process_tick()
        logger.info("✅ Monitoring loop processed tick successfully without crashing.")
        
        logger.info("All Guardian AI tests passed successfully! 🚀")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_tests())
