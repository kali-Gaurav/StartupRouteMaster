import sys, os
# ensure backend package root is on sys.path (script runs from backend/scripts)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from etl.sqlite_to_postgres import SQLiteReader, DEFAULT_SQLITE_PATH, PostgresLoader
r = SQLiteReader(DEFAULT_SQLITE_PATH)
segs = r.read_segment_data()
print('segs len', len(segs))
seg0 = segs[0]
print('seg0 sample', seg0)
loader = PostgresLoader(os.environ.get('DATABASE_URL') or os.environ.get('DB_URL') or 'postgresql://postgres:postgres@127.0.0.1:55432/postgres')
sts = r.read_stations_master()
print('stations_master count', len(sts))
mapping = {s['station_code']: loader.get_or_create_station(s['station_code'], s['station_name'], s['city'], s.get('latitude'), s.get('longitude')) for s in sts}
print('mapping size', len(mapping))
print('sample lookup', seg0['source_station_code'], '->', mapping.get(seg0['source_station_code']))
vid = loader.get_or_create_vehicle(seg0['train_no'], seg0['operator'])
print('vehicle id created', vid)
from backend.models import Segment
seg_id = loader.create_segment({
    'id':'test-seg-1',
    'source_station_id': mapping.get(seg0['source_station_code']),
    'dest_station_id': mapping.get(seg0['dest_station_code']),
    'vehicle_id': vid,
    'transport_mode':'train',
    'departure_time': seg0['departure_time'],
    'arrival_time': seg0['arrival_time'],
    'duration_minutes': seg0['duration_minutes'],
    'distance_km': seg0['distance_km'],
    'arrival_day_offset': seg0['arrival_day_offset'],
    'cost': seg0['cost'],
    'operating_days': seg0['operating_days']
})
print('created seg id', seg_id)
loader.db.commit()
loader.close()
from backend.database import SessionLocal
from backend.models import Vehicle, Segment
s=SessionLocal()
print('vehicles=', s.query(Vehicle).filter(Vehicle.vehicle_number==seg0['train_no']).count())
print('segments=', s.query(Segment).filter(Segment.id=='test-seg-1').count())
s.close()
