
import asyncio
import logging
from datetime import datetime
import sys
import os
from collections import Counter

# Ensure backend is in path
sys.path.insert(0, os.path.abspath("backend"))

from database.session import initialize_database_pools, SessionTransit
from core.route_engine.engine import route_engine
from core.route_engine.constraints_engine import ConstraintsEngine
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from services.search_service import SearchService

async def test_integrated_search_logic():
    print("🚀 Testing Integrated Search Logic (Direct Class Call)")
    await initialize_database_pools()
    
    # 2026-04-02 was the date used in test_all_engines.py
    travel_date = "2026-04-02"
    dt = datetime.strptime(travel_date, "%Y-%m-%d")
    
    # Init graph
    graph = await route_engine._get_current_graph(dt)
    
    db = SessionTransit()
    service = SearchService(db)
    
    pairs = [
        ("NDLS", "MMCT"),
        ("HWH", "MAS"),
        ("SBC", "PUNE")
    ]
    
    for src, dst in pairs:
        print(f"\n📍 Searching {src} -> {dst}...")
        
        start = datetime.now()
        try:
            # We call search_routes directly
            # This simulates the full API logic including orchestrator cluster resolution
            result = await service.search_routes(
                source=src,
                destination=dst,
                travel_date=travel_date,
                budget_category="standard",
                limit=15
            )
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if result.get("status") == "success":
                journeys = result.get("data", {}).get("journeys", [])
                total = result.get("total_available", 0)
                
                engines_used = Counter()
                transfer_counts = Counter()
                
                for j in journeys:
                    eng = j.get("metadata", {}).get("engine", "unknown")
                    engines_used[eng] += 1
                    
                    t_count = len(j.get("transfers", []))
                    transfer_counts[t_count] += 1
                
                print(f" ✅ Success in {duration:.2f}ms. Found {len(journeys)} journeys (Total Avail: {total})")
                print(f" 🛠 Engines involved: {dict(engines_used)}")
                print(f" 🔄 Transfers breakdown: {dict(transfer_counts)}")
            else:
                print(f" ❌ Failed: {result.get('error') or result.get('message')}")
        except Exception as e:
            print(f" ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    db.close()

if __name__ == "__main__":
    asyncio.run(test_integrated_search_logic())
