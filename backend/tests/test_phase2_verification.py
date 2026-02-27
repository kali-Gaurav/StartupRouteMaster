import asyncio
from datetime import date
from services.verification_engine import VerificationService
from core.segment_detail import JourneyOption, SegmentDetail

async def test_verification():
    print("\n🔍 Phase 2: Testing Verification Service...")
    service = VerificationService()
    
    # Create a mock JourneyOption based on the search result we know exists
    # Train T12951, NDLS -> MMCT
    journey = JourneyOption(
        journey_id="test_ndls_mmct",
        segments=[
            SegmentDetail(
                segment_id="1",
                train_number="T12951",
                train_name="NDLS-MMCT Rajdhani Express",
                depart_station="New Delhi",
                depart_code="NDLS",
                depart_time="16:55",
                depart_platform="1",
                arrival_station="Mumbai Central",
                arrival_code="MMCT",
                arrival_time="08:30",
                arrival_platform="1",
                distance_km=1384.0,
                travel_time_hours=15.5,
                travel_time_mins=935,
                running_days="Daily",
                halt_times={},
                ac_first_available=10,
                ac_second_available=20,
                ac_third_available=30,
                sleeper_available=40,
                base_fare=1393.95,
                tatkal_applicable=True
            )
        ],
        start_date="2026-03-15",
        end_date="2026-03-16",
        total_distance_km=1384.0,
        total_travel_time_mins=935,
        num_segments=1,
        num_transfers=0,
        cheapest_fare=1393.95,
        premium_fare=2500.0,
        is_direct=True,
        has_overnight=True,
        availability_status="AVAILABLE"
    )
    
    travel_date = date(2026, 3, 15)
    
    print(f"Verifying journey {journey.journey_id} for {travel_date}...")
    try:
        details = await service.verify_journey(
            journey=journey,
            travel_date=travel_date,
            coach_preference="AC_THREE_TIER"
        )
        
        print("\n✅ Verification Results:")
        print(f"Status: {details.overall_status}")
        print(f"Is Bookable: {details.is_bookable}")
        print(f"Seat Status: {details.seat_verification.status} ({details.seat_verification.available_seats} available)")
        print(f"Schedule: {details.schedule_verification.status} ({details.schedule_verification.message})")
        print(f"Fare: {details.fare_verification.total_fare} INR")
        
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_verification())
