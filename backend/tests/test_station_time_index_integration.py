import uuid
from datetime import datetime, time

from backend.database import SessionLocal, Base, engine_write
from backend.database.models import Stop, TimeIndexKey, StopDepartureBucket
from backend.station_time_index import StationTimeIndex
from backend.core.route_engine import TimeDependentGraph


def test_stop_time_index_used_by_graph():
    Base.metadata.create_all(bind=engine_write)
    db = SessionLocal()

    # create a GTFS stop (integer PK)
    stop = Stop(id=12345, stop_id='TEST_STOP_12345', code='T123', name='TestStop', city='TestCity', latitude=0.0, longitude=0.0)
    db.add(stop)
    db.commit()

    # create TimeIndexKey for a trip (trip_id = 999)
    k = TimeIndexKey(entity_type='trip', entity_id=str(999))
    db.add(k)
    db.commit()
    db.refresh(k)

    # create a stop_departure bucket for 08:00 (480)
    from pyroaring import BitMap
    bm = BitMap([k.id])
    blob = bm.serialize()

    bucket = StopDepartureBucket(id=str(uuid.uuid4()), stop_id=12345, bucket_start_minute=8 * 60, bitmap=blob, trips_count=1)
    db.add(bucket)
    db.commit()

    # Prepare graph with a matching departure event for trip 999 at 08:05
    graph = TimeDependentGraph()
    depart_dt = datetime.now().replace(hour=8, minute=5, second=0, microsecond=0)
    graph.departures_by_stop[12345] = [(depart_dt, 999)]

    # Attach in-memory index and query
    idx = StationTimeIndex(db)
    graph.station_time_index = idx

    res = graph.get_departures_from_stop(12345, depart_dt.replace(minute=0))
    assert any(tid == 999 for (_dt, tid) in res)

    db.close()
