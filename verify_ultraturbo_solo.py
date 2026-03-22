
import asyncio
import logging
from datetime import datetime, date
import sys
import os

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ultraturbo-solo-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from utils.station_utils import resolve_stations
from database.session import SessionTransit

async def audit_ultraturbo():
    print("--- ULTRATURBO SOLO AUDIT ---")
    
    # 1. Initialize DB
    await container.get('db')
    db = SessionTransit()
    
    engine = UltraTurboDirectEngine()
    
    # Pair to test: NDLS -> BCT
    src_code, dst_code = "NDLS", "BCT"
    departure_date = date(2026, 3, 21) # Saturday
    
    # Step A: Check station resolution
    src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
    print(f"Resolved {src_code}: ID={src_stop.id}, Name={src_stop.name}")
    print(f"Resolved {dst_code}: ID={dst_stop.id}, Name={dst_stop.name}")
    
    # Step B: Check if these IDs exist in stop_times
    import sqlite3
    db_path = "backend/database/transit_graph.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT count(*) FROM stop_times WHERE stop_id = ?", (src_stop.id,))
    print(f"Stop Times for {src_code} ({src_stop.id}): {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT count(*) FROM stop_times WHERE stop_id = ?", (dst_stop.id,))
    print(f"Stop Times for {dst_code} ({dst_stop.id}): {cursor.fetchone()[0]}")
    
    # Step C: Run Engine with Debug
    print("\nRunning UltraTurbo Engine find_routes...")
    routes = await engine.find_routes(src_stop.id, dst_stop.id, departure_date, limit=10)
    print(f"Yield: {len(routes)} routes")
    
    if len(routes) == 0:
        print("\n--- DEBUGGING INTERNAL SQL ---")
        # Check day mapping
        day_name = engine.day_map[departure_date.weekday()]
        print(f"Day detected: {day_name} (Weekday Index: {departure_date.weekday()})")
        
        # Check calendar for this day
        cursor.execute(f"SELECT count(*) FROM calendar WHERE {day_name} = 1")
        print(f"Services active on {day_name}: {cursor.fetchone()[0]}")
        
        # Check direct trip intersection without calendar join
        query = f"SELECT count(*) FROM stop_times s1 JOIN stop_times s2 ON s1.trip_id = s2.trip_id WHERE s1.stop_id = {src_stop.id} AND s2.stop_id = {dst_stop.id} AND s1.stop_sequence < s2.stop_sequence"
        cursor.execute(query)
        print(f"Direct raw trip intersections: {cursor.fetchone()[0]}")

    conn.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(audit_ultraturbo())
