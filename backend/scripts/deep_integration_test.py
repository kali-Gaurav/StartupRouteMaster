import asyncio
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.session import SessionLocal
from services.search_service import SearchService
from services.seat_verification import SeatVerificationService
from services.realtime_ingestion.live_status_service import LiveStatusService

# Configure logging to be visible
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("DeepIntegrationTest")

async def run_deep_test():
    # 0. Connection Pre-Check
    print(f"\n{'='*80}")
    print(f"🔍 PRE-TEST CONNECTION CHECK")
    print(f"{'='*80}")
    
    from services.seat_verification import SeatVerificationService
    from services.realtime_ingestion.live_status_service import LiveStatusService
    
    seat_svc = SeatVerificationService()
    live_svc = LiveStatusService()
    
    # RapidAPI Heartbeat
    try:
        api_check = await seat_svc.get_train_schedule("12002")
        if api_check:
            print("✅ RapidAPI Connection: OK")
        else:
            print("❌ RapidAPI Connection: FAILED (Check Key/Quota)")
            return
    except Exception as e:
        print(f"❌ RapidAPI Error: {e}")
        return

    db: Session = SessionLocal()
    search_service = SearchService(db)
    
    test_pairs = [
        ("CSMT", "MAO", "Known DB Route (Konkan)"),
        ("NDLS", "BCT", "Major Hub (Live Fallback Test)"),
        ("SBC", "MAS", "Regional South"),
        ("HWH", "CSMT", "Cross-Country East-West"),
        ("GHY", "TVC", "Extreme Distance (Hybrid Test)")
    ]
    
    travel_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"\n{'='*80}")
    print(f"🚀 STARTING DEEP INTEGRATION TEST")
    print(f"Target Date: {travel_date}")
    print(f"{'='*80}\n")

    for src, dst, label in test_pairs:
        print(f"📍 TESTING: {label} [{src} -> {dst}]")
        start_time = time.time()
        
        try:
            # 1. Internal Route Generation (Waterfall: Turbo -> FastPath -> RAPTOR)
            result = await search_service.search_routes(
                source=src,
                destination=dst,
                travel_date=travel_date,
                limit=5
            )
            
            latency = (time.time() - start_time) * 1000
            journeys = result.get("journeys", [])
            
            print(f"   ✅ Found {len(journeys)} routes in {latency:.2f}ms")
            
            if journeys:
                top = journeys[0]
                engine = top.get("engine_used", "UNKNOWN")
                conf = top.get("confidence_score", 0)
                train_no = top['legs'][0]['train_number']
                
                print(f"   🏷️ Primary Engine: {engine}")
                print(f"   🛡️ Confidence Score: {conf}%")
                
                # 2. Verify with RapidAPI IRCTC (Seat Verification)
                print(f"   🔍 Verifying Seat & Schedule (RapidAPI) for Train {train_no}...")
                seat_start = time.time()
                
                # Full verification including schedule and bulk cache
                is_avail = await seat_svc.verify_journey(top)
                
                seat_lat = (time.time() - seat_start) * 1000
                print(f"      -> Final Status: {top.get('availability_status', 'N/A')}")
                print(f"      -> Integrity Verified: {top.get('is_verified', False)}")
                print(f"      -> Latency: {seat_lat:.2f}ms")
                
                # Prove Caching: Check if the data is now in Redis
                from core.redis import async_redis_client
                cache_key = f"schedule:{train_no}"
                cached_sched = await async_redis_client.get(cache_key)
                if cached_sched:
                    print(f"      💾 Schedule Cache: VERIFIED (Redis)")
                
                # 3. Verify with Rappid URL (Live Status)
                print(f"   📡 Verifying Live Status (Rappid.in) for Train {train_no}...")
                live_start = time.time()
                live_data = await live_svc.get_live_status(train_no)
                live_lat = (time.time() - live_start) * 1000
                
                if live_data:
                    print(f"      -> Status: {live_data.get('status_message', 'Unknown')}")
                    print(f"      -> Current Position: {live_data.get('position', 'Unknown')}")
                    print(f"      -> Delay: {live_data.get('delay_minutes', 0)} mins | Latency: {live_lat:.2f}ms")
                else:
                    print(f"      -> Live Status Unavailable")

            else:
                print(f"   ⚠️ No routes found for this pair.")
                
        except Exception as e:
            print(f"   ❌ Test Failed for {src}->{dst}: {str(e)}")
            logger.exception("Error in deep test")
            
        print(f"{'-'*40}")

    print(f"\n{'='*80}")
    print(f"✅ DEEP INTEGRATION TEST COMPLETE")
    print(f"{'='*80}\n")
    
    await seat_svc.close_session()
    await live_svc.close_session()
    db.close()

if __name__ == "__main__":
    asyncio.run(run_deep_test())
