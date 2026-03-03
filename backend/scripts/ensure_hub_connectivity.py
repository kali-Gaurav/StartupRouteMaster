"""
[Hub Connectivity] ensure_hub_connectivity.py (TODO #28)

Identifies major hubs that are 'isolated' (few connections to other hubs)
and suggests/validates transfer links.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.snapshot_manager import SnapshotManager
from database.session import SessionLocal
from database.models import StationRank, Stop, Transfer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub-connectivity")

async def ensure_connectivity():
    sm = SnapshotManager()
    target_date = datetime.now()
    
    logger.info("Loading active snapshot for connectivity analysis...")
    snapshot = await sm.load_snapshot(target_date)
    if not snapshot:
        logger.error("No snapshot found. Build graph first.")
        return

    session = SessionLocal()
    try:
        # 1. Get all Major Hubs
        hubs = session.query(StationRank).filter(StationRank.hub_type == "major_hub").all()
        hub_ids = {h.station_id for h in hubs}
        hub_map = {h.station_id: h for h in hubs}
        
        logger.info(f"Analyzing network reachability for {len(hub_ids)} major hubs...")
        
        isolated_hubs = []
        
        for hid in hub_ids:
            reachable_hubs = set()
            # Check departures from this hub
            deps = snapshot.departures_by_stop.get(hid, [])
            
            for dt, tid in deps:
                # Get all stations this trip visits
                path_stations = {p['station_id'] for p in snapshot.train_path.get(tid, [])}
                # Intersect with other hubs
                found = path_stations.intersection(hub_ids)
                if hid in found: found.remove(hid)
                reachable_hubs.update(found)
            
            if len(reachable_hubs) < 3: # Heuristic: a major hub should reach at least 3 others
                isolated_hubs.append((hid, len(reachable_hubs)))

        if isolated_hubs:
            logger.warning(f"Found {len(isolated_hubs)} isolated major hubs:")
            for hid, count in isolated_hubs[:10]:
                stop = session.query(Stop).get(hid)
                logger.warning(f"  - Hub {stop.code if stop else hid} ({stop.name if stop else '??'}): reaches only {count} other hubs.")
                
                # TODO #28: Suggest/Auto-generate a transfer to the nearest hub if within 10km
                # (Implementation would use haversine_distance and add to 'transfers' table)
        else:
            logger.info("✅ Network graph is well-connected between major hubs.")

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(ensure_connectivity())
