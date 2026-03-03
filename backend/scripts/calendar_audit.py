"""
Utility to audit calendar coverage.

Usage:
    python calendar_audit.py 2026-03-01            # single date
    python calendar_audit.py 2026-03-01 2026-03-07   # range inclusive

Prints any trips whose service_id does not appear in the calendar table or in
calendar_dates for the given date(s). This helps catch ETL bugs where a train
was written but its service pattern was never stored.

"""

import sys
from datetime import datetime, timedelta, date

import sys, os
# ensure backend package is importable when run from workspace root
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.session import SessionLocal
from database.models import Trip, Calendar, CalendarDate


def find_missing_for_date(session, target_date: date):
    # subqueries for service_ids present
    cal_q = session.query(Calendar.service_id).subquery()
    caldate_q = session.query(CalendarDate.service_id).filter(CalendarDate.date == target_date).subquery()

    missing = (
        session.query(Trip)
        .filter(
            ~Trip.service_id.in_(cal_q),
            ~Trip.service_id.in_(caldate_q),
        )
        .all()
    )
    return missing


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)

    try:
        start = parse_date(argv[1])
    except Exception as e:
        print(f"Could not parse date '{argv[1]}': {e}")
        sys.exit(1)

    end = start
    if len(argv) == 3:
        try:
            end = parse_date(argv[2])
        except Exception as e:
            print(f"Could not parse end date '{argv[2]}': {e}")
            sys.exit(1)

    session = SessionLocal()
    try:
        current = start
        while current <= end:
            missing = find_missing_for_date(session, current)
            print(f"\n=== {current.isoformat()} ({len(missing)} missing services) ===")
            for trip in missing:
                print(f"trip_id={trip.trip_id}, service_id={trip.service_id}")
            current += timedelta(days=1)
    finally:
        session.close()


if __name__ == "__main__":
    main(sys.argv)
