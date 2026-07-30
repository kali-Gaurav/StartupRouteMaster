import uuid
from pyroaring import BitMap
from database import SessionLocal, Base, engine_write
from database.models import Station, TimeIndexKey, StationDepartureBucket
from station_time_index import StationTimeIndex


def test_station_time_index_build_and_query():
    Base.metadata.create_all(bind=engine_write)
    db = SessionLocal()

    station_id = str(uuid.uuid4())
    s = Station(id=station_id, name='TST', city='TestCity', latitude=12.0, longitude=77.0)
    db.add(s)
    db.commit()

    # create two time-index keys with known integer ids
    k1 = TimeIndexKey(entity_type='vehicle', entity_id='V1')
    k2 = TimeIndexKey(entity_type='vehicle', entity_id='V2')
    db.add_all([k1, k2])
    db.commit()
    db.refresh(k1)
    db.refresh(k2)

    bm = BitMap([k1.id, k2.id])
    blob = bm.serialize()

    bucket = StationDepartureBucket(
        id=str(uuid.uuid4()), station_id=station_id, bucket_start_minute=8 * 60,
        bitmap=blob, trips_count=2
    )
    db.add(bucket)
    db.commit()

    idx = StationTimeIndex(db)
    res = idx.query(station_id, minute_of_day=8 * 60, lookahead_minutes=15)
    ids = {r['entity_id'] for r in res}
    assert ids == {'V1', 'V2'}

    db.close()
