import asyncio
import logging
import sys
import os
from datetime import date, datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.verification_engine import verification_service
from core.segment_detail import JourneyOption, SegmentDetail
from core.container import container

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_unified_verification():
    logger.info("Starting Final Unification Verification Test")
    
    # Initialize database container
    try:
        logger.info("Initializing database container...")
        await container.get("db")
        logger.info("Database container initialized.")
    except Exception as e:
        logger.warning(f"Database initialization failed (ignoring for standalone test): {e}")

    # Mock a journey option with correct dataclass arguments
    segment = SegmentDetail(
        segment_id="seg_19038_bvi_ndls",
        train_number="19038",
        train_name="AVADH EXPRESS",
        depart_station="BORIVALI",
        depart_code="BVI",
        depart_time="22:35",
        depart_platform="6",
        arrival_station="NEW DELHI",
        arrival_code="NDLS",
        arrival_time="03:40",
        arrival_platform="5",
        distance_km=1384.0,
        travel_time_hours=15.5,
        travel_time_mins=932,
        running_days="1111111",
        halt_times={},
        ac_first_available=5,
        ac_second_available=10,
        ac_third_available=15,
        sleeper_available=0,
        base_fare=2500.0,
        tatkal_applicable=True
    )
    
    journey = JourneyOption(
        journey_id="test_journey_123",
        segments=[segment],
        start_date="2026-04-15",
        end_date="2026-04-16",
        total_distance_km=1384.0,
        total_travel_time_mins=932,
        num_segments=1,
        num_transfers=0,
        cheapest_fare=2500.0,
        premium_fare=4500.0,
        is_direct=True,
        has_overnight=True,
        availability_status="AVAILABLE"
    )
    
    travel_date = date(2026, 4, 15)
    
    try:
        logger.info(f"Verifying journey {journey.journey_id} for train {segment.train_number}...")
        details = await verification_service.verify_journey(
            journey=journey,
            travel_date=travel_date,
            coach_preference="AC_THREE_TIER"
        )
        
        logger.info("--- Verification Results ---")
        logger.info(f"Overall Status: {details.overall_status}")
        logger.info(f"Is Bookable: {details.is_bookable}")
        
        logger.info(f"Seat Status: {details.seat_verification.status}")
        logger.info(f"Available Seats: {details.seat_verification.available_seats}")
        logger.info(f"Seat Message: {details.seat_verification.message}")
        
        logger.info(f"Schedule Status: {details.schedule_verification.status}")
        logger.info(f"Delay: {details.schedule_verification.delay_minutes} mins")
        logger.info(f"Schedule Message: {details.schedule_verification.message}")
        
        logger.info(f"Fare Status: {details.fare_verification.status}")
        logger.info(f"Total Fare: {details.fare_verification.total_fare}")
        logger.info(f"Fare Message: {details.fare_verification.message}")
        
        if details.warnings:
            logger.warning(f"Warnings: {details.warnings}")
        if details.restrictions:
            logger.warning(f"Restrictions: {details.restrictions}")
            
        logger.info("Verification Test Passed Successfully!")
        
    except Exception as e:
        logger.error(f"Verification Test Failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_unified_verification())
