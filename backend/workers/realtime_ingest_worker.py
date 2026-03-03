"""
[Missing Logic #7] realtime_ingest_worker.py

Worker logic to ingest real-time overlay data into StationTrainHistory 
and synchronize the active RealtimeOverlay state.
"""

import logging
from datetime import datetime, date, time
from typing import Dict, Any

from database.session import SessionLocal
from database.models import StationTrainHistory, Trip, Stop
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("realtime-ingest")

async def process_realtime_update(data: Dict[str, Any]):
    """
    Processes a single real-time update for a train at a station.
    
    Expected data:
    {
        "train_number": "12622",
        "station_code": "MAS",
        "delay_minutes": 15,
        "actual_arrival": "2026-03-03 22:15:00",
        "is_cancelled": False
    }
    """
    session = SessionLocal()
    try:
        train_no = str(data.get("train_number"))
        station_code = str(data.get("station_code"))
        delay = int(data.get("delay_minutes", 0))
        
        # 1. Resolve Trip and Stop IDs
        trip = session.query(Trip).filter(Trip.trip_id == train_no).first()
        stop = session.query(Stop).filter(Stop.code == station_code).first()
        
        if not trip or not stop:
            logger.warning(f"Could not resolve trip {train_no} or stop {station_code}")
            return

        # 2. Record in StationTrainHistory (TODO #29)
        today = date.today()
        
        # Upsert history record
        history = session.query(StationTrainHistory).filter(
            StationTrainHistory.trip_id == trip.id,
            StationTrainHistory.station_id == stop.id,
            StationTrainHistory.date == today
        ).first()
        
        if not history:
            history = StationTrainHistory(
                trip_id=trip.id,
                station_id=stop.id,
                date=today
            )
            session.add(history)
            
        history.delay_minutes = delay
        history.is_cancelled = data.get("is_cancelled", False)
        
        if data.get("actual_arrival"):
            try:
                dt = datetime.fromisoformat(data["actual_arrival"])
                history.actual_arr = dt.time()
            except: pass
            
        session.commit()
        
        # 3. Synchronize Real-time Overlay via Redis (Phase 10)
        # In a real system, we'd update a global overlay object in Redis.
        await multi_layer_cache.initialize()
        overlay_data = await multi_layer_cache.get_overlay_state() or {"delays": {}, "cancellations": []}
        
        # Phase 4: Observability - Track hit rate (TODO #36)
        # Check if this delay actually matters to our current graph
        snapshot = await multi_layer_cache.get_graph_snapshot(today.strftime('%Y%m%d'))
        if snapshot:
            hit = "NO"
            if hasattr(snapshot, 'trip_segments') and trip.id in snapshot.trip_segments:
                hit = "YES"
            
            # Update metric in Redis
            hit_key = f"metrics:delay_hits:{today.strftime('%Y%m%d')}"
            if hit == "YES":
                await multi_layer_cache.redis.hincrby(hit_key, "hits", 1)
            else:
                await multi_layer_cache.redis.hincrby(hit_key, "misses", 1)
                
            logger.info(f"Observability (TODO #36): Real-time update for {train_no} hit active snapshot? {hit}")

        # Update delay for the trip
        overlay_data["delays"][str(trip.id)] = delay
        if history.is_cancelled:
            if str(trip.id) not in overlay_data["cancellations"]:
                overlay_data["cancellations"].append(str(trip.id))
        
        await multi_layer_cache.set_overlay_state("current", overlay_data)
        logger.info(f"Ingested real-time update for {train_no} at {station_code}: {delay}m delay")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to ingest real-time update: {e}")
    finally:
        session.close()
