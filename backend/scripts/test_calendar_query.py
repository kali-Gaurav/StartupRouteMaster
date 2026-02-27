from datetime import datetime, date
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker
import os
from database.models import Calendar

db_path = os.path.normpath(os.path.join(os.getcwd(), "backend", "database", "transit_graph.db"))
engine = create_engine(f"sqlite:///{db_path}")
Session = sessionmaker(bind=engine)
session = Session()

target_date = date(2026, 3, 11)
weekday = "wednesday"

try:
    # Test 1: Exact True
    res1 = session.query(Calendar.service_id).filter(
        and_(
            getattr(Calendar, weekday) == True,
            Calendar.start_date <= target_date,
            Calendar.end_date >= target_date
        )
    ).all()
    print(f"Test 1 (== True): {res1}")

    # Test 2: or_(== True, == 1)
    res2 = session.query(Calendar.service_id).filter(
        and_(
            or_(getattr(Calendar, weekday) == True, getattr(Calendar, weekday) == 1),
            Calendar.start_date <= target_date,
            Calendar.end_date >= target_date
        )
    ).all()
    print(f"Test 2 (or True/1): {res2}")

    # Test 3: Raw check of the record
    cal = session.query(Calendar).first()
    print(f"Record: wed={cal.wednesday} (type: {type(cal.wednesday)})")

finally:
    session.close()
