import asyncio
import logging
import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database.session import SessionLocal
from services.search_service import SearchService
from services.seat_verification import SeatVerificationService
from services.realtime_ingestion.live_status_service import LiveStatusService

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("AccuracyTest")

# Diverse test routes covering various regions and complexities
TEST_ROUTES = [
    ("NDLS", "BCT", "Major Hub Direct"),
    ("SBC", "MAS", "South Regional Hub"),
    ("HWH", "CSMT", "East-West Cross Country"),
    ("PGT", "BNC", "South Transfer Expected"),
    ("GHY", "TVC", "Extreme Long Distance"),
    ("LKO", "CNB", "Short Distance Direct"),
    ("PNBE", "NDLS", "High Density Route"),
    ("ADI", "ST", "Gujarat Express Corridor"),
    ("BBS", "RNC", "East Coast Route"),
    ("CSMT", "MAO", "Konkan Railway")
]

async def check_truth(train_no, date_str, seat_svc, live_svc, src, dst):
    """
    Checks the 'live truth' of a train from DB against RapidAPI and Rappid.in
    Returns: (is_running, is_available, delay_mins)
    """
    is_running = False
    is_available = False
    delay_mins = 0
    
    # 1. Check Schedule (Does it exist and stop at these stations?)
    try:
        schedule = await seat_svc.get_train_schedule(train_no)
        if schedule and schedule.get("stationList"):
            codes = [s.get("stationCode") for s in schedule.get("stationList", [])]
            if src in codes and dst in codes:
                is_running = True
    except Exception as e:
        logger.warning(f"Schedule error for {train_no}: {e}")

    # 2. Check Seat Availability (Is it bookable?)
    if is_running:
        try:
            avail_data = await seat_svc.check_segment(train_no, src, dst, date_str)
            if avail_data and avail_data.get("available", False):
                is_available = True
        except Exception:
            pass

    # 3. Check Live Status (Is it heavily delayed/cancelled?)
    if is_running:
        try:
            live = await live_svc.get_live_status(train_no)
            if live:
                if "cancel" in live.get("status_message", "").lower():
                    is_running = False # Ghost train that got cancelled today
                delay_mins = live.get("delay_minutes", 0)
        except Exception:
            pass

    return is_running, is_available, delay_mins

async def run_accuracy_validation():
    print(f"\n{'='*60}")
    print(f"🚄 ROUTE ENGINE ACCURACY & TRUTH VALIDATION")
    print(f"{'='*60}")
    
    db: Session = SessionLocal()
    search_svc = SearchService(db)
    seat_svc = SeatVerificationService()
    live_svc = LiveStatusService()
    
    # Check connections first
    api_check = await seat_svc.get_train_schedule("12002")
    if not api_check:
        print("❌ RapidAPI Connection Failed. Please check quota/key.")
        return
    print("✅ External APIs Connected.")

    travel_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"Target Travel Date: {travel_date}\n")

    results = []
    
    stats = {
        "total_generated": 0,
        "verified_running": 0,
        "verified_available": 0,
        "high_delay": 0,
        "ghost_routes": 0,
        "engine_perf": {}
    }

    for src, dst, desc in TEST_ROUTES:
        print(f"🔍 Testing [{src} -> {dst}] - {desc}")
        
        # CLEAR SESSION CACHE TO ENSURE FRESH API CALLS
        seat_svc.clear_session_cache()
        
        start_search = time.time()
        # USE force_refresh=True to bypass cached search results and force fresh API/Enrichment
        res = await search_svc.search_routes(src, dst, travel_date, limit=5, force_refresh=True)
        search_time = (time.time() - start_search) * 1000
        
        journeys = res.get("journeys", [])
        
        engine_used = "NONE"
        if journeys:
            engine_used = journeys[0].get("engine_used", "UNKNOWN")
        
        if engine_used not in stats["engine_perf"]:
            stats["engine_perf"][engine_used] = {"count": 0, "avg_lat": 0}
        
        stats["engine_perf"][engine_used]["count"] += 1
        stats["engine_perf"][engine_used]["avg_lat"] += search_time
            
        print(f"   ↳ Engine: {engine_used} | Search & API Verification Time: {search_time:.2f}ms")
        
        if not journeys:
            print("      ⚠️ No routes found by any engine.")
            continue

        for idx, j in enumerate(journeys):
            stats["total_generated"] += 1
            train_no = j['legs'][0]['train_number']
            
            # Key Metrics from SearchService enrichment
            is_valid = j.get("is_verified", False)
            status_text = j.get("availability_status", "UNKNOWN")
            live = j.get("live_status", {})
            delay = live.get("delay", 0)
            
            # LOGIC: If is_verified is False, it means the API couldn't confirm the train path
            status_symbol = "✅" if is_valid else "👻 GHOST"
            avail_symbol = "🎫" if "AVAILABLE" in status_text.upper() else "🚫"
            
            print(f"      [{idx+1}] Train {train_no}: {status_symbol} | Seats: {avail_symbol} ({status_text}) | Delay: {delay}m")
            
            if is_valid:
                stats["verified_running"] += 1
            else:
                stats["ghost_routes"] += 1
                
            if "AVAILABLE" in status_text.upper():
                stats["verified_available"] += 1
                
            if delay > 60:
                stats["high_delay"] += 1
                
            results.append({
                "Source": src,
                "Destination": dst,
                "Train": train_no,
                "Engine": engine_used,
                "Is_Running": is_valid,
                "Is_Available": "AVAILABLE" in status_text.upper(),
                "Delay_Mins": delay,
                "Confidence": j.get("confidence_score", 0)
            })
            
        print("-" * 40)

    # Calculate final metrics
    total = max(1, stats["total_generated"])
    acc_run = (stats["verified_running"] / total) * 100
    acc_seat = (stats["verified_available"] / total) * 100
    ghost_rate = (stats["ghost_routes"] / total) * 100

    print(f"\n{'='*60}")
    print(f"📊 FINAL INTEGRATION & ACCURACY REPORT")
    print(f"{'='*60}")
    print(f"Total Routes Generated : {stats['total_generated']}")
    print(f"Actually Running (True) : {stats['verified_running']}")
    print(f"Ghost Routes (Static DB) : {stats['ghost_routes']}")
    print(f"Seats Available        : {stats['verified_available']}")
    print(f"High Delay (>60m)      : {stats['high_delay']}")
    print(f"--------------------------------------------------")
    print(f"🔥 Running Accuracy    : {acc_run:.1f}%")
    print(f"🎫 Seat Availability   : {acc_seat:.1f}%")
    print(f"👻 Discard/Ghost Rate  : {ghost_rate:.1f}%")
    print(f"--------------------------------------------------")
    print("Engine Latency Performance:")
    for eng, p in stats["engine_perf"].items():
        avg = p["avg_lat"] / p["count"]
        print(f"   -> {eng}: {avg:.2f}ms (over {p['count']} searches)")
    print(f"{'='*60}\n")
    
    df = pd.DataFrame(results)
    df.to_csv("backend/accuracy_report.csv", index=False)
    print("💾 Saved detailed results to backend/accuracy_report.csv")

    await seat_svc.close_session()
    await live_svc.close_session()
    db.close()

if __name__ == "__main__":
    asyncio.run(run_accuracy_validation())