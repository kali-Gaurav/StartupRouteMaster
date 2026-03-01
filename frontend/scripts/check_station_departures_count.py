from backend.database import SessionLocal
from backend.database.models import StationDepartureBucket

if __name__ == '__main__':
    s = SessionLocal()
    print('station_departures rows =', s.query(StationDepartureBucket).count())
    s.close()
