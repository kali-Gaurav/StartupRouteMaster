import asyncio
import logging
from datetime import datetime, timedelta
from database.session import SessionLocal
from database.models import Stop, Trip, StopTime, Calendar, Segment, Transfer
from core.route_engine.builder import GraphBuilder
from core.route_engine.engine import RailwayRouteEngine
from core.route_engine.constraints import RouteConstraints
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_workflow_steps():
    db = SessionLocal()
    engine = RailwayRouteEngine()
    
    # Target Date: Next Wednesday
    today = datetime.now()
    target_date = today + timedelta(days=(2 - today.weekday()) % 7 + 7)
    target_date = target_date.replace(hour=10, minute=0, second=0, microsecond=0)
    
    logger.info(f"=== STEP 1: DATABASE INTEGRITY CHECK ({target_date.date()}) ===")
    try:
        stop_count = db.query(Stop).count()
        trip_count = db.query(Trip).count()
        calendar_count = db.query(Calendar).count()
        segment_count = db.query(Segment).count()
        transfer_count = db.query(Transfer).count()
        
        logger.info(f"Stops: {stop_count}")
        logger.info(f"Trips: {trip_count}")
        logger.info(f"Calendar: {calendar_count}")
        logger.info(f"Segments: {segment_count}")
        logger.info(f"Transfers: {transfer_count}")
        
        if transfer_count == 0:
            logger.warning("CRITICAL: No transfers found in database! Multi-segment routing will fail.")

        # Check for active services on target date
        weekday = target_date.strftime('%A').lower()
        active_services = db.query(Calendar.service_id).filter(
            getattr(Calendar, weekday) == True,
            Calendar.start_date <= target_date.date(),
            Calendar.end_date >= target_date.date()
        ).count()
        logger.info(f"Active services on {target_date.date()} ({weekday}): {active_services}")

    except Exception as e:
        logger.error(f"Step 1 failed: {e}")

    logger.info("=== STEP 2: GRAPH BUILDING ===")
    try:
        graph = await engine._get_current_graph(target_date)
        snapshot = graph.snapshot
        
        logger.info(f"Snapshot stops: {len(snapshot.stop_cache)}")
        logger.info(f"Snapshot trip segments: {len(snapshot.trip_segments)}")
        logger.info(f"Snapshot departures indexed: {sum(len(v) for v in snapshot.departures_by_stop.values())}")
        
        # Check specific station (ABR)
        abr = db.query(Stop).filter(Stop.stop_id == 'ABR').first()
        if abr:
            deps = graph.get_departures_from_stop(abr.id, target_date)
            logger.info(f"Departures from ABR (id={abr.id}) on {target_date}: {len(deps)}")
            if deps:
                logger.info(f"Sample Departure: {deps[0]}")
        else:
            logger.error("ABR station not found in DB!")

    except Exception as e:
        logger.error(f"Step 2 failed: {e}")

    logger.info("=== STEP 3: RAPTOR ROUND 0 (DIRECT) ===")
    try:
        src_code = "ABR"
        dest_code = "ADI"
        
        src_stop = db.query(Stop).filter(Stop.stop_id == src_code).first()
        dest_stop = db.query(Stop).filter(Stop.stop_id == dest_code).first()
        
        if src_stop and dest_stop:
            constraints = RouteConstraints(max_transfers=0)
            # Call the internal _search_single_departure to see what happens in Round 0
            routes = await engine.raptor._search_single_departure(graph, src_stop.id, dest_stop.id, target_date, constraints)
            logger.info(f"Round 0 found {len(routes)} routes.")
            for r in routes[:2]:
                logger.info(f"  Route: {len(r.segments)} segments, Arrival: {r.segments[-1].arrival_time}")
        else:
            logger.error(f"Station codes {src_code} or {dest_code} invalid.")

    except Exception as e:
        logger.error(f"Step 3 failed: {e}")

    logger.info("=== STEP 4: TRANSFER DISCOVERY ===")
    try:
        if abr:
            transfers = graph.get_transfers_from_stop(abr.id, target_date, 15)
            logger.info(f"Transfers from ABR (id={abr.id}): {len(transfers)}")
            for t in transfers[:3]:
                logger.info(f"  To {t.station_name} (sid={t.station_id}) in {t.duration_minutes} mins")
    except Exception as e:
        logger.error(f"Step 4 failed: {e}")

    db.close()

if __name__ == "__main__":
    asyncio.run(debug_workflow_steps())
