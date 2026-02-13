import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@127.0.0.1:55432/postgres'

from database import Base, engine, SessionLocal
from models import Station, Vehicle, Segment

# create tables
Base.metadata.create_all(bind=engine)

# run ETL
from etl.sqlite_to_postgres import run_etl
run_etl()

# verify counts
s = SessionLocal()
print('stations=', s.query(Station).count())
print('vehicles=', s.query(Vehicle).count())
print('segments=', s.query(Segment).count())
s.close()
