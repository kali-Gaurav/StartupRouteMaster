import pandas as pd
import json
import os
from datetime import datetime
from routemaster_agent.database.db import SessionLocal, engine
from routemaster_agent.database.models import TrainMaster, TrainStation, LiveStatus
from .data_cleaner import clean_schedule, clean_live_status

class DataPipeline:
    def __init__(self):
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)

    def save_to_files(self, data, prefix):
        timestamp = datetime.now().strftime("%Y%m%d")

        # Save JSON
        json_path = f"{self.output_dir}/{prefix}_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        # Save CSV (flattening logic for lists/dicts)
        if isinstance(data, list):
            df = pd.DataFrame(data)
            df.to_csv(f"{self.output_dir}/{prefix}_{timestamp}.csv", index=False)

    def save_batch_schedules(self, schedules: list):
        """Save batch schedules as schedules_YYYYMMDD.json and schedules_YYYYMMDD.csv (flattened stations)."""
        timestamp = datetime.now().strftime("%Y%m%d")
        json_path = f"{self.output_dir}/schedules_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(schedules, f, indent=2, default=str)

        rows = []
        for s in schedules:
            train_no = s.get('train_no') or s.get('train_number')
            for st in s.get('schedule', []) or []:
                row = {
                    'train_number': train_no,
                    'sequence': st.get('sequence'),
                    'station_code': st.get('station_code'),
                    'station_name': st.get('station_name'),
                    'day': st.get('day'),
                    'arrival': st.get('arrival'),
                    'departure': st.get('departure'),
                    'halt_minutes': st.get('halt_minutes'),
                    'distance_km': st.get('distance_km')
                }
                rows.append(row)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(f"{self.output_dir}/schedules_{timestamp}.csv", index=False)

    def save_batch_live(self, lives: list):
        timestamp = datetime.now().strftime("%Y%m%d")
        json_path = f"{self.output_dir}/live_status_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(lives, f, indent=2, default=str)

        if lives:
            df = pd.DataFrame(lives)
            df.to_csv(f"{self.output_dir}/live_status_{timestamp}.csv", index=False)

    async def update_database(self, schedule_data, live_data):
        """Simple upsert logic using SQLAlchemy (synchronous DB calls wrapped in async function).
        - Replaces station list for a train.
        - Upserts TrainMaster and LiveStatus.
        """
        if not schedule_data or 'train_no' not in schedule_data:
            return False

        # ensure data is cleaned
        schedule_data = clean_schedule(schedule_data)
        if live_data:
            live_data = clean_live_status(live_data)

        train_no = schedule_data['train_no']
        session = SessionLocal()
        try:
            # TrainMaster upsert
            tm = session.get(TrainMaster, train_no)
            if not tm:
                tm = TrainMaster(
                    train_number=train_no,
                    train_name=schedule_data.get('name'),
                    source=schedule_data.get('source'),
                    destination=schedule_data.get('destination'),
                    days_of_run=schedule_data.get('days_of_run'),
                    type=schedule_data.get('type'),
                    updated_at=datetime.utcnow(),
                )
                session.add(tm)
            else:
                tm.train_name = schedule_data.get('name') or tm.train_name
                tm.source = schedule_data.get('source') or tm.source
                tm.destination = schedule_data.get('destination') or tm.destination
                tm.days_of_run = schedule_data.get('days_of_run') or tm.days_of_run
                tm.type = schedule_data.get('type') or tm.type
                tm.updated_at = datetime.utcnow()

            # Replace stations (simple approach)
            session.query(TrainStation).filter(TrainStation.train_number == train_no).delete()
            stations_to_add = []
            for seq, s in enumerate(schedule_data.get('schedule', []), start=1):
                distance = None
                try:
                    distance = float(s.get('distance_km')) if s.get('distance_km') is not None else None
                except Exception:
                    distance = None

                st = TrainStation(
                    train_number=train_no,
                    station_code=s.get('station_code'),
                    station_name=s.get('station_name'),
                    sequence=s.get('sequence') or seq,
                    arrival=s.get('arrival'),
                    departure=s.get('departure'),
                    halt_minutes=s.get('halt_minutes'),
                    distance_km=distance,
                    day_count=s.get('day')
                )
                stations_to_add.append(st)

            if stations_to_add:
                session.add_all(stations_to_add)

            # LiveStatus upsert
            if live_data:
                ls = session.get(LiveStatus, train_no)
                if not ls:
                    ls = LiveStatus(
                        train_number=train_no,
                        current_station=live_data.get('current_station'),
                        status=live_data.get('status') or 'UNKNOWN',
                        delay_minutes=live_data.get('delay_minutes') or 0,
                        next_station=live_data.get('next_station'),
                        eta_next=live_data.get('eta_next'),
                        last_updated_ts=datetime.utcnow()
                    )
                    session.add(ls)
                else:
                    ls.current_station = live_data.get('current_station') or ls.current_station
                    ls.delay_minutes = live_data.get('delay_minutes') or ls.delay_minutes
                    ls.last_updated_ts = datetime.utcnow()

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print("update_database failed:", e)
            return False
        finally:
            session.close()
