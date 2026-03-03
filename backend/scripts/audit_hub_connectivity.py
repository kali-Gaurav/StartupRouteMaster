"""
[Hub Connectivity] audit_hub_connectivity.py (TODO #27)

Measures if hubs are disconnected from the network and logs gaps.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.route_engine.snapshot_manager import SnapshotManager
from database.session import SessionLocal
from database.models import StationRank, Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub-audit")

async def audit_hubs():
    sm = SnapshotManager()
    target_date = datetime.now()
    
    logger.info("Loading active snapshot...")
    snapshot = await sm.load_snapshot(target_date)
    if not snapshot:
        logger.error("No snapshot found.")
        return

    session = SessionLocal()
    try:
        # Get all major hubs and junctions
        hubs = session.query(StationRank).filter(StationRank.hub_type.in_(["major_hub", "junction"])).all()
        hub_ids = [h.station_id for h in hubs]
        
        logger.info(f"Auditing connectivity for {len(hub_ids)} hubs...")
        
        disconnected = []
        for hid in hub_ids:
            # Check if this hub has departures or arrivals in the snapshot
            deps = snapshot.departures_by_stop.get(hid, [])
            arrs = snapshot.arrivals_by_stop.get(hid, [])
            
            if not deps and not arrs:
                disconnected.append(hid)
        
        if disconnected:
            logger.warning(f"Found {len(disconnected)} hubs with NO graph activity:")
            for hid in disconnected[:10]:
                stop = session.query(Stop).get(hid)
                logger.warning(f"  - Hub {hid} ({stop.code if stop else '??'}): {stop.name if stop else '??'}")
        else:
            logger.info("✅ All hubs have active connections in the current graph.")

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(audit_hubs())
