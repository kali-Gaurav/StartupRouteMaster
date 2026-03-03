"""
[Missing Logic #8] calculate_station_ranks.py

Calculates station connectivity scores based on an active graph snapshot
and classifies them into hubs (major_hub, junction, regular).
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.snapshot_manager import SnapshotManager
from database.session import SessionTransit as SessionLocal
from database.models import StationRank, Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("station-ranker")

async def calculate_ranks():
    sm = SnapshotManager()
    target_date = datetime.now()
    
    logger.info(f"Loading snapshot for {target_date.date()} to calculate ranks...")
    snapshot = await sm.load_snapshot(target_date)
    
    if not snapshot:
        logger.error("No snapshot found. Build a graph first.")
        return

    # Calculate Degree Centrality (how many distinct trips pass through each station)
    # Using departures + arrivals as a proxy for connectivity
    connectivity = defaultdict(int)
    
    # departures_by_stop: stop_id -> list of (time, trip_id)
    for sid, deps in snapshot.departures_by_stop.items():
        connectivity[sid] += len(deps)
        
    for sid, arrs in snapshot.arrivals_by_stop.items():
        connectivity[sid] += len(arrs)

    if not connectivity:
        logger.error("Snapshot contains no connectivity data.")
        return

    # Rank stations
    sorted_stations = sorted(connectivity.items(), key=lambda x: x[1], reverse=True)
    max_conn = sorted_stations[0][1]
    
    logger.info(f"Top station: {snapshot.stop_cache.get(sorted_stations[0][0]).name} with {max_conn} connections")

    session = SessionLocal()
    try:
        from sqlalchemy import delete
        session.execute(delete(StationRank))
        
        rank_records = []
        for sid, score in sorted_stations:
            # Classification logic
            # Top 1% or > 200 connections = major_hub
            # Top 5% or > 50 connections = junction
            # Others = regular
            
            # Simple threshold-based for now
            hub_type = "regular"
            if score > 300:
                hub_type = "major_hub"
            elif score > 100:
                hub_type = "junction"
            
            # Use Stop model to check if it's already marked as major_junction
            stop = snapshot.stop_cache.get(sid)
            if stop and getattr(stop, 'is_major_junction', False) and hub_type == "regular":
                hub_type = "junction"

            record = StationRank(
                station_id=sid,
                connectivity_score=float(score),
                hub_type=hub_type
            )
            rank_records.append(record)
            
        session.add_all(rank_records)
        session.commit()
        logger.info(f"Successfully ranked and classified {len(rank_records)} stations.")
        
        # Summary
        major_hubs = [r for r in rank_records if r.hub_type == "major_hub"]
        junctions = [r for r in rank_records if r.hub_type == "junction"]
        logger.info(f"Classification Summary: {len(major_hubs)} major hubs, {len(junctions)} junctions.")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Ranking failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(calculate_ranks())
