
import asyncio
import logging
from datetime import datetime, date
import sys
import os
import sqlite3

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ultraturbo-deep-audit")

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from core.container import container
from core.route_engine.ultra_turbo import UltraTurboDirectEngine
from utils.station_utils import resolve_stations
from database.session import SessionTransit

async def audit_ultraturbo_yield():
    print("--- ULTRATURBO DEEP YIELD AUDIT (BPL -> HBJ) ---")
    
    await container.get('db')
    db = SessionTransit()
    engine = UltraTurboDirectEngine()
    
    src_code, dst_code = "BPL", "HBJ"
    departure_date = date(2026, 3, 21) # Saturday
    
    src_stop, dst_stop = resolve_stations(db, src_code, dst_code)
    print(f"Resolved {src_code}: ID={src_stop.id}, Code={src_stop.code}")
    print(f"Resolved {dst_code}: ID={dst_stop.id}, Code={dst_stop.code}")
    
    if not src_stop.id or not dst_stop.id:
        print("CRITICAL: Numeric IDs are missing!")
        return

    # 1. Run Engine
    routes = await engine.find_routes(src_code, dst_code, departure_date, limit=50)
    print(f"\nInitial Engine Yield: {len(routes)} routes")

    # 2. Manual SQL Audit
    db_path = "backend/database/transit_graph.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    day_name = engine.day_map[departure_date.weekday()]
    db_date = departure_date.strftime("%Y%m%d")
    
    print(f"\nAnalyzing SQL Components for {day_name} ({db_date}):")
    
    # Check 1: Direct trip connection in stop_times
    query_raw = f"""
        SELECT count(*) 
        FROM stop_times s1 
        JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
        WHERE s1.stop_id = {src_stop.id} 
          AND s2.stop_id = {dst_stop.id} 
          AND s1.stop_sequence < s2.stop_sequence
    """
    cursor.execute(query_raw)
    print(f"  1. Raw Trip Connections (no calendar): {cursor.fetchone()[0]}")
    
    # Check 2: With Calendar JOIN
    query_cal = f"""
        SELECT count(*) 
        FROM stop_times s1 
        JOIN stop_times s2 ON s1.trip_id = s2.trip_id 
        JOIN trips t ON s1.trip_id = t.id
        JOIN calendar c ON t.service_id = c.service_id
        WHERE s1.stop_id = {src_stop.id} 
          AND s2.stop_id = {dst_stop.id} 
          AND s1.stop_sequence < s2.stop_sequence
          AND c.{day_name} = 1
          AND '{db_date}' BETWEEN c.start_date AND c.end_date
    """
    cursor.execute(query_cal)
    print(f"  2. Active Connections on {day_name}: {cursor.fetchone()[0]}")

    if cursor.fetchone() is None:
        # Check if BPL and HBJ are in the same cluster
        print("\nChecking Clusters...")
        cursor.execute("SELECT cluster_id FROM station_cluster_mapping WHERE station_id = ?", (src_stop.id,))
        src_clusters = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT cluster_id FROM station_cluster_mapping WHERE station_id = ?", (dst_stop.id,))
        dst_clusters = [r[0] for r in cursor.fetchall()]
        print(f"  BPL Clusters: {src_clusters}")
        print(f"  HBJ Clusters: {dst_clusters}")

    conn.close()
    db.close()

if __name__ == "__main__":
    asyncio.run(audit_ultraturbo_yield())
