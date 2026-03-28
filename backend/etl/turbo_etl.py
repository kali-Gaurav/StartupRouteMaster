import sqlite3
import logging
import asyncio
import os
import uuid
import sys
import gc
from datetime import datetime, time, date
from typing import List, Dict, Any

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import text, insert
from database.session import SessionTransit as SessionLocal, engine_transit as engine
from database.models import (
    Stop, Trip, Route, Agency, Calendar, StopTime, Segment, 
    Vehicle, StationSchedule, TrainPath, ETLMetadata, TrainMaster
)
from core.nexus.audit.governor import nexus_governor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("turbo-etl")

def parse_time(t_str):
    if not t_str: return time(12, 0)
    try:
        if ' ' in t_str: t_str = t_str.split(' ')[1] 
        parts = t_str.split(':')
        return time(int(parts[0]) % 24, int(parts[1]))
    except: return time(12, 0)

async def run_turbo_etl():
    """[Task 106] Elite Resource-Aware ETL Ingestion."""
    db_path = os.path.join('backend', 'database', 'railway_data.db')
    if not os.path.exists(db_path):
         db_path = os.path.join('database', 'railway_data.db')
         
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    session = SessionLocal()
    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    
    try:
        etl_meta = ETLMetadata(run_id=run_id, status="running", source_version="v1.0")
        session.add(etl_meta)
        session.commit()
        
        logger.info(f"Starting Optimized ETL Run: {run_id}")
        agency = session.query(Agency).filter(Agency.agency_id == "IR").first()
        if not agency:
            agency = Agency(agency_id="IR", name="Indian Railways", url="https://enquiry.indianrail.gov.in", timezone="Asia/Kolkata")
            session.add(agency)
            session.flush()
        
        # [Nexus Optimization] Partial Memory Load
        station_mapping = {s[1]: s[0] for s in session.query(Stop.id, Stop.stop_id).all()}
        existing_trips = {t for t in session.query(Trip.trip_id).scalars().all()}
        existing_calendars = {c for c in session.query(Calendar.service_id).scalars().all()}
        existing_routes = {r[0]: r[1] for r in session.query(Route.route_id, Route.id).all()}
        
        trains = [dict(r) for r in conn.execute("SELECT * FROM trains_master").fetchall()]
        running_days_map = {r['train_no']: dict(r) for r in conn.execute("SELECT * FROM train_running_days").fetchall()}
        
        # [Elite Restoration] Synchronize TrainMaster for FTS5 Search
        logger.info(f"Syncing {len(trains)} trains to TrainMaster index...")
        existing_train_master = {tm for tm in session.query(TrainMaster.train_number).scalars().all()}
        tm_to_add = []
        for t in trains:
            t_no = str(t['train_no'])
            if t_no not in existing_train_master:
                tm_to_add.append(TrainMaster(train_number=t_no, train_name=t['train_name']))
        
        if tm_to_add:
            session.add_all(tm_to_add)
            session.flush()
            logger.info(f"Added {len(tm_to_add)} new trains to Master Search Index.")

        new_trains = [t for t in trains if str(t['train_no']) not in existing_trips]
        if not new_trains:
            logger.info("✅ All systems synced. Nothing new.")
            return

        DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        BATCH_SIZE = 50

        for i in range(0, len(new_trains), BATCH_SIZE):
            # 1. GOVERNOR PULSE CHECK [Task 106]
            stats = await nexus_governor.get_stats()
            if stats["throttle_factor"] > 0.75:
                 logger.warning(f"⚖️ [ETL:GOVERNOR] High Pressure ({stats['throttle_factor']*100:.1f}%). Throttling Ingestion.")
                 await asyncio.sleep(8)
                 if stats["throttle_factor"] > 0.9:
                      logger.error("🛑 [ETL:ABORT] Critical memory depletion. Safe stop.")
                      break

            batch = new_trains[i:i+BATCH_SIZE]
            logger.info(f"Ingesting Batch {i//BATCH_SIZE + 1}...")
            
            vehicles_to_add, stop_times_to_add, segments_to_add = [], [], []
            station_schedules_to_add, train_paths_to_add = [], []

            for t in batch:
                train_no = str(t['train_no'])
                
                # Route/Trip Orchestration
                if train_no not in existing_routes:
                    gr = Route(route_id=train_no, agency_id=agency.id, short_name=train_no, long_name=t['train_name'], route_type=2)
                    session.add(gr); session.flush()
                    existing_routes[train_no] = gr.id
                
                route_id_internal = existing_routes[train_no]
                running = running_days_map.get(train_no)
                service_id = f"S_{train_no}" if running else "DAILY"
                
                if running and service_id not in existing_calendars:
                    cal = Calendar(
                        service_id=service_id, monday=bool(running['mon']), tuesday=bool(running['tue']), 
                        wednesday=bool(running['wed']), thursday=bool(running['thu']),
                        friday=bool(running['fri']), saturday=bool(running['sat']), sunday=bool(running['sun']),
                        start_date=date(2020,1,1), end_date=date(2030,12,31)
                    )
                    session.add(cal); existing_calendars.add(service_id)

                trip = Trip(trip_id=train_no, route_id=route_id_internal, service_id=service_id)
                session.add(trip); session.flush()
                
                vehicle_id = str(uuid.uuid4())
                vehicles_to_add.append({"id": vehicle_id, "vehicle_number": train_no, "type": 'train', "operator": 'IR'})

                # Station Pulse
                route_rows = conn.execute("SELECT * FROM train_routes WHERE train_no = ? ORDER BY seq_no", (train_no,)).fetchall()
                for j, curr in enumerate(route_rows):
                    code = curr['station_code']
                    if code not in station_mapping: continue
                    
                    sid = station_mapping[code]
                    arr, dep = parse_time(curr['arrival_time']), parse_time(curr['departure_time'])
                    
                    stop_times_to_add.append({
                        "trip_id": trip.id, "stop_id": sid, "arrival_time": arr, "departure_time": dep, "stop_sequence": curr['seq_no']
                    })
                    
                    for day in DAYS_OF_WEEK:
                        payload = {"station_id": sid, "trip_id": trip.id, "arrival": arr, "departure": dep, "day_of_week": day, "stop_seq": curr['seq_no']}
                        station_schedules_to_add.append(payload)
                        train_paths_to_add.append(payload)

                    if j < len(route_rows) - 1:
                        nxt = route_rows[j+1]
                        if nxt['station_code'] in station_mapping:
                            dur = (nxt['cumulative_travel_minutes'] or 0) - (curr['cumulative_travel_minutes'] or 0)
                            segments_to_add.append({
                                "id": str(uuid.uuid4()), "source_station_id": sid, "dest_station_id": station_mapping[nxt['station_code']],
                                "trip_id": trip.id, "vehicle_id": vehicle_id, "transport_mode": 'train',
                                "departure_time": dep, "arrival_time": parse_time(nxt['arrival_time']),
                                "arrival_day_offset": nxt['day_offset'] or 0, "duration_minutes": dur if dur > 0 else 60,
                                "distance_km": float((nxt['distance_from_source'] or 0) - (curr['distance_from_source'] or 0)),
                                "operating_days": "1111111"
                            })

                etl_meta.trips_synced += 1

            # Flush Batch
            session.bulk_insert_mappings(Vehicle, vehicles_to_add)
            session.bulk_insert_mappings(StopTime, stop_times_to_add)
            session.bulk_insert_mappings(Segment, segments_to_add)
            session.bulk_insert_mappings(StationSchedule, station_schedules_to_add)
            session.bulk_insert_mappings(TrainPath, train_paths_to_add)
            session.commit()
            
            # [Task 112] Strict Memory Pruning
            del vehicles_to_add, stop_times_to_add, segments_to_add
            del station_schedules_to_add, train_paths_to_add
            gc.collect()

        etl_meta.status = "success"
        etl_meta.end_time = datetime.utcnow()
        session.commit()
        logger.info(f"🚀 Turbo ETL Phase 106 Success. {etl_meta.trips_synced} trips active.")

    except Exception as e:
        logger.error(f"❌ ETL Failure: {e}")
        session.rollback()
        if 'etl_meta' in locals():
            etl_meta.status = "failed"
            etl_meta.end_time = datetime.utcnow()
            session.commit()
        raise
    finally:
        session.close(); conn.close()

if __name__ == "__main__":
    asyncio.run(run_turbo_etl())
